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
equal('metadata.version from frontmatter', skill.metadata && skill.metadata.version, '1.3.8');
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
  join('scripts', 'run_evals.py'),
  join('scripts', 'check_review_form.py'),
  join('scripts', 'check_skill.py'),
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

const declared = plugin.SKILL_NAMES.slice();
plugin.apply(ctx);
equal('apply registers every declared skill', registrations.length, declared.length);
equal('declared skills are shipped', declared.join(','), 'project-dept,loop-ops');
for (const name of declared) {
  const registered = registrations.find((item) => item.name === name) ?? {};
  const dir = plugin.skillDirOf(name);
  const definition = plugin.loadSkill(dir);
  check(`registered skill "${name}" has a body`, typeof registered.content === 'string' && registered.content.trim().length > 200, String(registered.content || '').slice(0, 20));
  check(`registered skill "${name}" description matches its file`, registered.description === definition.description);
  check(`registered skill "${name}" keeps its resourceBase`, registered.resourceBase && registered.resourceBase.path === dir, JSON.stringify(registered.resourceBase));
  check(`registered skill "${name}" carries metadata.version`, Boolean(registered.metadata && registered.metadata.version), JSON.stringify(registered.metadata));
  const missingOwn = [...definition.content.matchAll(/(?:^|[\s`(])((?:static|references|scripts|tests|evals|agents)\/[A-Za-z0-9._/-]+|manifest\.yaml)/g)]
    .map((match) => match[1].split(/[),。；]/)[0])
    .filter((relative) => relative.endsWith('.md') || relative.endsWith('.py') || relative.endsWith('.json') || relative.endsWith('.yaml'))
    .filter((relative) => !existsSync(join(dir, relative)));
  check(`files declared by "${name}" exist in the bundle`, missingOwn.length === 0, `missing=${missingOwn.join(', ')}`);
}
const projectDept = registrations.find((item) => item.name === 'project-dept') ?? {};
equal('project-dept metadata version', projectDept.metadata && projectDept.metadata.version, '1.3.8');
const loopOps = registrations.find((item) => item.name === 'loop-ops') ?? {};
equal('loop-ops metadata version', loopOps.metadata && loopOps.metadata.version, '1.0.0');
check('loop-ops declares its dependency on project-dept', String(loopOps.metadata && loopOps.metadata.requires) === 'project-dept', JSON.stringify(loopOps.metadata));
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
check('skillDirOf resolves a bundled skill', plugin.skillDirOf('loop-ops') === join(ROOT, 'skills', 'loop-ops'), plugin.skillDirOf('loop-ops'));
check('bundle ships the loop-ops SKILL.md', existsSync(join(ROOT, 'skills', 'loop-ops', 'SKILL.md')));

// The packaged body must not drift from the SKILL.md the bundle advertises.
const raw = readFileSync(join(SKILL_DIR, 'SKILL.md'), 'utf8');
check('shipped SKILL.md declares the manifest version', raw.includes('version: 1.3.8'), 'frontmatter changed');

process.stdout.write(`\n${passed}/${passed + failures.length} passed\n`);
if (failures.length > 0) {
  process.stdout.write(`failures:\n${failures.map((item) => ` - ${item}`).join('\n')}\n`);
  process.exit(1);
}
process.stdout.write(`disposer invoked on teardown: ${disposed}\n`);