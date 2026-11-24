// Bundle integrity tests: the skill ships inside the package, so every file the
// body tells the model to read must actually exist next to it, and the host half
// must hand the registry a complete definition.

import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import * as plugin from '../index.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const SKILL_DIR = join(ROOT, 'skills', 'project-dept');

let passed = 0;
const failures = [];

function check(label, condition, detail) {
  if (condition) {
    passed += 1;
    process.stdout.write(`PASS ${label}\n`);
    return;
  }
  failures.push(detail === undefined ? label : `${label} — ${detail}`);
  process.stdout.write(`FAIL ${label}${detail === undefined ? '' : ` — ${detail}`}\n`);
}

function equal(label, actual, expected) {
  check(label, actual === expected, `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

// ---------------------------------------------------------------- loadSkill
const skill = plugin.loadSkill();

equal('skill name', skill.name, 'project-dept');
check('description is routing-grade', typeof skill.description === 'string' && skill.description.length > 60, `len=${skill.description && skill.description.length}`);
check('body does not carry frontmatter', !skill.content.startsWith('---'), skill.content.slice(0, 20));
check('body starts with the heading', skill.content.startsWith('# project-dept'), skill.content.slice(0, 24));
equal('metadata.version from frontmatter', skill.metadata && skill.metadata.version, '1.0.14');
check('metadata.tags parsed as a list', Array.isArray(skill.metadata && skill.metadata.tags) && skill.metadata.tags.length === 5, JSON.stringify(skill.metadata && skill.metadata.tags));
check('path points at the shipped SKILL.md', skill.path === join(SKILL_DIR, 'SKILL.md'), skill.path);
check('resourceBase is the skill directory', skill.resourceBase.kind === 'directory' && skill.resourceBase.path === SKILL_DIR, JSON.stringify(skill.resourceBase));
equal('whenToUse absent when frontmatter omits it', skill.whenToUse, undefined);

// ------------------------------------------------------------ frontmatter
const plain = plugin.__test__.splitFrontmatter('# heading\n\nbody');
equal('splitFrontmatter leaves text without frontmatter alone', plain.body, '# heading\n\nbody');
equal('splitFrontmatter reports empty frontmatter', plain.front, '');

const bom = plugin.__test__.splitFrontmatter('\uFEFF---\nname: x\n---\nbody');
equal('splitFrontmatter tolerates a UTF-8 BOM', bom.body.trim(), 'body');

let threw = false;
try {
  plugin.__test__.parseFrontmatter('name: ok\nthis line is not yaml');
} catch {
  threw = true;
}
check('parseFrontmatter rejects malformed lines', threw);

const folded = plugin.__test__.parseFrontmatter('name: x\ndescription: >\n  one\n  two');
equal('parseFrontmatter joins folded scalars', folded.description, 'one two');

// ------------------------------------------------- declared files exist
const mentioned = new Set();
const pathPattern = /(?:^|[\s`(])((?:static|references|scripts|tests|evals|agents)\/[A-Za-z0-9._/-]+\.(?:md|py|json|yaml))|manifest\.yaml/g;
for (const match of skill.content.matchAll(pathPattern)) {
  mentioned.add(match[1] ?? match[0]);
}
check('body references files', mentioned.size > 5, `found=${mentioned.size}`);
const missing = [...mentioned].filter((relative) => !existsSync(join(SKILL_DIR, relative)));
check('every file the body declares exists in the bundle', missing.length === 0, `missing=${missing.join(', ')}`);

const required = [
  'manifest.yaml',
  'README.md',
  'README_EN.md',
  'VERIFICATION.md',
  join('scripts', 'dept_gate.py'),
  join('scripts', 'check_doc.py'),
  join('static', 'core', 'principles.md'),
  join('static', 'core', 'workflow.md'),
  join('static', 'core', 'output-contract.md'),
  join('references', 'blind-review.md'),
];
const absent = required.filter((relative) => !existsSync(join(SKILL_DIR, relative)));
check('the core assets are packaged', absent.length === 0, `missing=${absent.join(', ')}`);

// ------------------------------------------------------------- host half
const registrations = [];
let disposed = 0;
const fakeSkills = {
  register(definition) {
    registrations.push(definition);
    return () => {
      disposed += 1;
    };
  },
};
const effects = [];
const ctx = {
  skills: fakeSkills,
  effect(callback) {
    effects.push(callback);
    return callback();
  },
};

plugin.apply(ctx);
equal('apply registers exactly one skill', registrations.length, 1);
const registered = registrations[0] ?? {};
equal('registered name', registered.name, 'project-dept');
check('registered body is the skill body', typeof registered.content === 'string' && registered.content.startsWith('# project-dept'), String(registered.content).slice(0, 20));
check('registered description matches the file', registered.description === skill.description);
check('registered resourceBase survives', registered.resourceBase && registered.resourceBase.path === SKILL_DIR, JSON.stringify(registered.resourceBase));
check('registered metadata survives', registered.metadata && registered.metadata.version === '1.0.14', JSON.stringify(registered.metadata));
check('apply runs through ctx.effect', effects.length === 1, String(effects.length));

let refused = false;
try {
  plugin.apply({ effect: () => {} });
} catch {
  refused = true;
}
check('apply refuses to start without the registry', refused);

const bound = plugin.__test__.DEFAULT_SKILL_DIR;
check('default skill directory is inside the package', bound === join(ROOT, 'skills', 'project-dept'), bound);
check('skill directory separator is native', bound.includes(sep), bound);

// The packaged body must not drift from the SKILL.md the bundle advertises.
const raw = readFileSync(join(SKILL_DIR, 'SKILL.md'), 'utf8');
check('shipped SKILL.md still declares version 1.0.14', raw.includes('version: 1.0.14'), 'frontmatter changed');

process.stdout.write(`\n${passed}/${passed + failures.length} passed\n`);
if (failures.length > 0) {
  process.stdout.write(`failures:\n${failures.map((item) => ` - ${item}`).join('\n')}\n`);
  process.exit(1);
}
process.stdout.write(`disposer invoked on teardown: ${disposed}\n`);