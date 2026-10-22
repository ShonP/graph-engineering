# Bootstrap snippets

Placeholders in angle brackets. Run once by the owner, then record the ids as repo variables.

## Azure: group, role, pipeline identity

```bash
GROUP_ID=$(az ad group create --display-name <group> --mail-nickname <group> --query id -o tsv)
az ad group member add --group "$GROUP_ID" --member-id <user-object-id>

az role assignment create --assignee-object-id "$GROUP_ID" --assignee-principal-type Group \
  --role "<narrowest built-in role>" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/<provider>/<type>/<name>

az identity create -g <rg> -n <identity>
CLIENT_ID=$(az identity show -g <rg> -n <identity> --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -g <rg> -n <identity> --query principalId -o tsv)

az identity federated-credential create -g <rg> --identity-name <identity> --name <repo>-default-branch \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:<owner>/<repo>:ref:refs/heads/<default-branch> \
  --audiences api://AzureADTokenExchange

az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "<narrowest built-in role>" --scope <resource scope>

gh variable set AZURE_CLIENT_ID --body "$CLIENT_ID"
gh variable set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
gh variable set AZURE_SUBSCRIPTION_ID --body "$(az account show --query id -o tsv)"
```

Offboarding: `az ad group member remove --group "$GROUP_ID" --member-id <user-object-id>`.

## GitHub workflow skeleton

```yaml
name: <pipeline>
on:
  workflow_dispatch:
    inputs:
      target:
        description: <what it targets>
        required: true
permissions:
  contents: read
  id-token: write
jobs:
  run:
    if: github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<full-commit-sha>
      - uses: azure/login@<full-commit-sha>
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - env:
          TARGET: ${{ inputs.target }}
        run: ./scripts/<task>.sh "$TARGET"
```

The federated subject pins the default branch ref, so a run from any other ref cannot exchange its token for an Azure token.

## Other clouds

- AWS: an IAM OIDC identity provider for `token.actions.githubusercontent.com` plus a role whose trust policy pins `sub` to the default branch; `aws-actions/configure-aws-credentials` with `role-to-assume`.
- GCP: Workload Identity Federation (pool and provider with an attribute condition on the repo and ref) and `google-github-actions/auth`.
