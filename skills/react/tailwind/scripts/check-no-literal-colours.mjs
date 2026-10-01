// Rules for check-no-literal-colours.sh; run through that wrapper. Written for
// tailwindcss 4.3.3: the utility list is every utility whose theme keys include
// --color (tailwindcss/dist/lib.js), the palettes are 4.3's defaults.
import fs from 'node:fs';
import path from 'node:path';

const die = (msg) => { console.error(`check-no-literal-colours: ${msg}`); process.exit(2); };
const [presetArg, ...paths] = process.argv.slice(2);
if (!presetArg || paths.length === 0) die('usage: check-no-literal-colours.sh <preset.css> <path>...');
for (const p of [presetArg, ...paths]) if (!fs.existsSync(p)) die(`no such file or directory: '${p}'`);

const preset = fs.readFileSync(presetArg, 'utf8');
const declared = new Set([...preset.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
if (![...declared].some((d) => /^--color-[a-z0-9]/.test(d))) die(`no --color-* token in ${presetArg}`);

const NAMED = 'aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen'.split(' ');
const PALETTES = 'slate gray zinc neutral stone mauve olive mist taupe red orange amber yellow lime green emerald teal cyan sky blue indigo violet purple fuchsia pink rose'.split(' ');
const NAMED_RE = new RegExp(`(?<![\\w-])(?:${NAMED.join('|')})(?![\\w-])`, 'i');
const colourWord = (v) => v === 'white' || v === 'black' || NAMED.includes(v)
  || new RegExp(`^(?:${PALETTES.join('|')})-\\d{2,3}$`).test(v);

const HEX = /(?<![&\w])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/g;
const FUNC = /(?<![\w-])(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch|color|color-mix|light-dark)\((?:[^()\n]|\([^()\n]*\))*\)/g;
// Substring tests (no ^$ anchors): a composite arbitrary value like `0_0_2px_#fff`
// (Tailwind's space-as-underscore) carries a hex/functional/named colour alongside
// non-colour parts, so the value as a whole is never just the colour.
const isColourValue = (v) => new RegExp(HEX.source).test(v) || new RegExp(FUNC.source).test(v) || NAMED_RE.test(v);

// Colour utilities, longest prefix first. Value: what follows the dash.
const UTIL = ['mask-(?:linear|radial|conic|[trblxy])-(?:from|to)', 'ring-offset', 'inset-ring', 'inset-shadow',
  'drop-shadow', 'text-shadow', 'border-b[se]', 'border-[xytrblse]', 'border', 'bg', 'text', 'divide', 'outline',
  'ring', 'shadow', 'accent', 'caret', 'fill', 'stroke', 'decoration', 'placeholder', 'from', 'via', 'to'];
const LEAD = String.raw`(?<![\w\-/.@#$\[,])`;
const WORD_UTIL = new RegExp(String.raw`${LEAD}(${UTIL.join('|')})-([a-z][a-z0-9-]*[a-z0-9]|[a-z])((?:/(?:\d+|\[[^\]\s]*\]|\([^)\s]*\)))?!?)(?![\w:\-/\[])`, 'g');
const ARB_UTIL = new RegExp(String.raw`${LEAD}(${UTIL.join('|')})-\[([^\]\s]+)\](?:/\d+)?!?`, 'g');
// Tailwind v4's `bg-(--color-brand)` shorthand: a bare CSS-variable reference,
// no `var()` wrapper. Only the `--color-*` namespace is checked (rule 4's scope).
const PAREN_UTIL = new RegExp(String.raw`${LEAD}(${UTIL.join('|')})-\((--color-[a-z0-9-]+)\)(?:/\d+)?!?`, 'g');
// A bare `var(--color-X)` anywhere (a style prop, a CSS declaration) - not just
// inside a utility class - naming a token the preset never declares.
const VAR_REF = /var\(\s*(--color-[a-z0-9-]+)\s*\)/g;

const SIZES = '2xs|xs|sm|md|lg|xl|2xl|none|inner';
const SIDE = String.raw`(?:[xytrblse]|b[se])(?:-\d+|-\[[^\]]+\]|-\(.+\))?`;
const NONCOLOUR = {
  bg: '(?:fixed|local|scroll|cover|contain|no-repeat|repeat(?:-.+)?|(?:clip|origin|size|position|blend|gradient)-.+|(?:top|bottom|left|right|center)(?:-.+)?|(?:linear|radial|conic)(?:-.+)?)',
  text: '(?:xs|sm|base|lg|xl|left|center|right|justify|start|end|wrap|nowrap|balance|pretty|ellipsis|clip|shadow)',
  border: `(?:solid|dashed|dotted|double|hidden|collapse|separate|spacing(?:-.+)?|${SIDE})`,
  divide: '(?:[xy](?:-.+)?|solid|dashed|dotted|double|hidden)',
  outline: '(?:hidden|solid|dashed|dotted|double|offset(?:-.+)?)',
  ring: '(?:inset|offset(?:-.+)?)',
  shadow: `(?:${SIZES})`, 'inset-shadow': `(?:${SIZES})`, 'drop-shadow': `(?:${SIZES})`, 'text-shadow': `(?:${SIZES})`,
  decoration: '(?:solid|double|dotted|dashed|wavy|from-font|clone|slice)',
};
const NAMESPACE = { text: '--text-', shadow: '--shadow-', 'inset-shadow': '--inset-shadow-', 'drop-shadow': '--drop-shadow-', 'text-shadow': '--text-shadow-' };

// SVG/HTML colour attributes: `fill="red"`, `stroke='white'`, `stopColor={'red'}`.
// Only quoted or `{'...'}` string literals - an unquoted `{expr}` is a variable,
// not a literal, and is left alone.
const SVG_ATTR = /(?<![\w-])(?:fill|stroke|color|stopColor|floodColor|lightingColor)=(?:"([^"\n]*)"|'([^'\n]*)'|\{(['"`])([^'"`\n]*)\3\})/g;
const ALLOWED_ATTR_VALUE = new Set(['currentColor', 'none', 'transparent', 'inherit']);
function attrValueBad(value) {
  if (ALLOWED_ATTR_VALUE.has(value)) return false;
  const varColour = value.match(/^var\((--color-[a-z0-9-]+)\)$/);
  if (varColour) return !declared.has(varColour[1]);
  return isColourValue(value);
}

function wordUtilOk(util, value) {
  if (['inherit', 'current', 'transparent', 'none', 'auto'].includes(value)) return true;
  if (declared.has(`--color-${value}`)) return true;
  const base = util.startsWith('border') ? 'border' : util;
  if (NAMESPACE[base] && declared.has(NAMESPACE[base] + value)) return true;
  if (NONCOLOUR[base] && new RegExp(`^${NONCOLOUR[base]}$`).test(value)) return true;
  // Gradient stops and mask stops also take positions; flag only colour words there.
  if (/^(?:from|via|to)$|^mask-/.test(util)) return !colourWord(value);
  return false;
}

// Blank out comments, URLs and non-class attribute values, keeping offsets and
// newlines. A URL is never a colour: `url(red.png)` and `'https://ex.com/#fff'`
// can spell a named colour or a hex-looking fragment by coincidence.
const blank = (s) => s.replace(/[^\n]/g, ' ');
function mask(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|\s)\/\/[^\n]*/g, (m, lead) => lead + blank(m.slice(lead.length)))
    .replace(/url\(([^)\n]*)\)/gi, (m, inner) => `url(${blank(inner)})`)
    .replace(/(["'`])((?:https?:)?\/\/[^"'`\n]*)\1/g, (m, q, inner) => q + blank(inner) + q)
    .replace(/(?<![\w-])(?:id|name|htmlFor|key|type|role|href|src|to|alt|title|placeholder|data-[\w-]+|aria-[\w-]+)=(?:"[^"\n]*"|'[^'\n]*'|\{\s*(["'`])[^"'`\n]*\1\s*\})/g, blank);
}

const JS_PROP = /(?<![\w-])['"]?([A-Za-z-]*(?:[cC]olor|fill|stroke|[sS]hadow|background|border|outline)[A-Za-z-]*)['"]?\s*:\s*(['"`])([^'"`\n]*)\2/g;
const CSS_DECL = /(?<![\w-])([a-z-]*(?:color|fill|stroke|shadow|background|border|outline)[a-z-]*)\s*:\s*([^;{}\n]*)/g;

function scan(file) {
  const text = mask(fs.readFileSync(file, 'utf8'));
  const css = file.endsWith('.css');
  const hits = [];
  const add = (m, show = m[0]) => hits.push({ start: m.index, end: m.index + m[0].length, show });
  for (const m of text.matchAll(HEX)) add(m);
  for (const m of text.matchAll(FUNC)) add(m);
  for (const m of text.matchAll(VAR_REF)) if (!declared.has(m[1])) add(m);
  for (const m of text.matchAll(SVG_ATTR)) {
    const value = m[1] ?? m[2] ?? m[4];
    if (value !== undefined && attrValueBad(value)) add(m);
  }
  if (css) {
    for (const m of text.matchAll(CSS_DECL)) if (NAMED_RE.test(m[2])) add(m, `${m[1]}: ${m[2].trim()}`);
  } else {
    for (const m of text.matchAll(JS_PROP)) if (NAMED_RE.test(m[3])) add(m);
  }
  // Utilities: anywhere in script files; only on @apply lines in CSS.
  const regions = css ? [...text.matchAll(/@apply[^;\n]*/g)] : [{ 0: text, index: 0 }];
  for (const r of regions) {
    for (const m of r[0].matchAll(WORD_UTIL)) if (!wordUtilOk(m[1], m[2])) add({ ...m, index: r.index + m.index });
    for (const m of r[0].matchAll(ARB_UTIL)) {
      const v = m[2].replace(/^color:/, '');
      const varColour = v.match(/^var\((--color-[a-z0-9-]+)\)$/);
      if (varColour) {
        if (!declared.has(varColour[1])) add({ ...m, index: r.index + m.index });
        continue;
      }
      if (!/^var\(--/.test(v) && isColourValue(v.replace(/_/g, ' '))) add({ ...m, index: r.index + m.index });
    }
    for (const m of r[0].matchAll(PAREN_UTIL)) if (!declared.has(m[2])) add({ ...m, index: r.index + m.index });
  }
  // Report the outermost span once: `text-[#f00]` is one violation, not two.
  hits.sort((a, b) => a.start - b.start || b.end - a.end);
  let reach = -1;
  const out = [];
  for (const h of hits) {
    if (h.start < reach) continue;
    reach = h.end;
    out.push(`${file}:${text.slice(0, h.start).split('\n').length}: ${h.show}`);
  }
  return out;
}

const SKIP = new Set(['node_modules', 'dist', 'build', '.next', '.turbo', 'coverage', '.git']);
const EXT = /\.(?:[cm]?[jt]sx?|css)$/;
const presetReal = fs.realpathSync(presetArg);
function* walk(p) {
  const st = fs.statSync(p);
  if (st.isFile()) { if (EXT.test(p) && fs.realpathSync(p) !== presetReal) yield p; return; }
  for (const e of fs.readdirSync(p, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.isDirectory() && SKIP.has(e.name)) continue;
    if (e.isDirectory() || e.isFile()) yield* walk(path.join(p, e.name));
  }
}

let scanned = 0;
let bad = 0;
for (const p of paths) {
  for (const f of walk(p)) {
    scanned += 1;
    for (const line of scan(f)) { console.log(line); bad += 1; }
  }
}
if (scanned === 0) die(`nothing to scan under: ${paths.join(', ')}`);
process.exit(bad ? 1 : 0);
