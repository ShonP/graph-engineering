"""Regression cases for vet_smoke.py. Stdlib only: python3 test_vet_smoke.py"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

VET = pathlib.Path(__file__).resolve().parent.parent / "vet_smoke.py"


def req(method: str, url: str, extra: str = "", tags: str = "smoke") -> str:
    return textwrap.dedent(
        f"""\
        meta {{
          name: r
          type: http
          tags: [{tags}]
        }}

        {method} {{
          url: {url}
        }}
        """
    ) + extra


class VetSmoke(unittest.TestCase):
    def run_vet(self, files: dict[str, str], tenant: str = "qa-tenant"):
        with tempfile.TemporaryDirectory() as d:
            for name, text in files.items():
                p = pathlib.Path(d, name)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
            args = [sys.executable, str(VET), d] + (["--test-tenant", tenant] if tenant is not None else [])
            r = subprocess.run(args, capture_output=True, text=True)
            return r.returncode, r.stdout

    def assert_refused(self, files, tenant="qa-tenant"):
        code, out = self.run_vet(files, tenant)
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSE", out)

    def test_get_runs(self):
        self.assertEqual(self.run_vet({"a.bru": req("get", "{{baseUrl}}/health")})[0], 0)

    def test_tenant_scoped_post_runs(self):
        code, out = self.run_vet({"a.bru": req("post", "{{baseUrl}}/tenants/{{testTenant}}/users")})
        self.assertEqual(code, 0, out)

    def test_tenant_scoped_post_refused_without_tenant(self):
        self.assert_refused({"a.bru": req("post", "{{baseUrl}}/tenants/{{testTenant}}/users")}, tenant="")

    def test_unscoped_write_refused(self):
        self.assert_refused({"a.bru": req("delete", "{{baseUrl}}/users?t={{testTenant}}")})

    def test_relative_segment_refused(self):
        self.assert_refused({"a.bru": req("post", "{{baseUrl}}/tenants/{{testTenant}}/../acme/users")})

    def test_second_method_block_refused(self):
        self.assert_refused({"a.bru": req("get", "{{baseUrl}}/x", "\ndelete {\n  url: {{baseUrl}}/x\n}\n")})

    def test_indented_second_method_block_refused(self):
        self.assert_refused({"a.bru": req("get", "{{baseUrl}}/x", "\n  delete {\n    url: {{baseUrl}}/x\n  }\n")})

    def test_script_changing_method_refused(self):
        extra = '\nscript:pre-request {\n  req.setMethod("DELETE");\n}\n'
        self.assert_refused({"a.bru": req("get", "{{baseUrl}}/x", extra)})

    def test_script_running_other_request_refused(self):
        extra = '\nscript:post-response {\n  await bru.runRequest("danger/wipe");\n}\n'
        self.assert_refused({"a.bru": req("get", "{{baseUrl}}/x", extra)})

    def test_folder_script_sending_request_refused(self):
        folder = 'meta {\n  name: f\n}\n\nscript:pre-request {\n  await bru.sendRequest({method: "DELETE"});\n}\n'
        self.assert_refused({"sub/folder.bru": folder, "sub/a.bru": req("get", "{{baseUrl}}/x")})

    def test_vars_block_rebinding_tenant_refused(self):
        extra = "\nvars:pre-request {\n  testTenant: acme-prod\n}\n"
        self.assert_refused({"a.bru": req("post", "{{baseUrl}}/tenants/{{testTenant}}/u", extra)})

    def test_setvar_rebinding_tenant_refused(self):
        extra = '\nscript:pre-request {\n  bru.setVar("testTenant", "acme-prod");\n}\n'
        self.assert_refused({"a.bru": req("post", "{{baseUrl}}/tenants/{{testTenant}}/u", extra)})

    def test_untagged_write_ignored(self):
        files = {"a.bru": req("get", "{{baseUrl}}/x"), "b.bru": req("delete", "{{baseUrl}}/x", tags="smoke-extended")}
        self.assertEqual(self.run_vet(files)[0], 0)

    def test_missing_collection_is_blocked(self):
        r = subprocess.run([sys.executable, str(VET), "/nonexistent-ge-collection"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_no_smoke_requests_is_blocked(self):
        self.assertEqual(self.run_vet({"a.bru": req("get", "{{baseUrl}}/x", tags="regression")})[0], 2)


if __name__ == "__main__":
    unittest.main()
