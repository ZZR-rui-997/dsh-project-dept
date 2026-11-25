// dsh-project-dept — ship the project-dept skills inside one bundle.
//
// Each skill body lives at ./skills/<name>/SKILL.md, next to this file.
// Scanning roots is not an option for a package that must work wherever the
// user installed it: @deepseek-ai/dsh-skill-filesystem resolves bundledSkillDir
// against the DSH process cwd, not against this package. So the host half
// registers the skill through the registry instead — ctx.skills.register() is
// the documented route for a plugin that carries its own skill, and the file
// path stays absolute, so relative references inside the body (SKILL.md points
// at manifest.yaml, static/, references/, scripts/) keep resolving.

import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
// Every skill this bundle carries, in registration order. Adding a skill means
// dropping a folder under ./skills and listing its SKILL.md `name` here.
export const SKILL_NAMES = Object.freeze(['project-dept', 'loop-ops']);
export const SKILL_NAME = SKILL_NAMES[0];
const SKILLS_DIR = join(HERE, 'skills');
const DEFAULT_SKILL_DIR = join(SKILLS_DIR, SKILL_NAME);

/** Directory of a bundled skill by name. */
export function skillDirOf(name) {
  return join(SKILLS_DIR, name);
}

/** Split `---\n…\n---\n body` into the frontmatter text and the body. */
function splitFrontmatter(source) {
  // The authored SKILL.md is saved with a UTF-8 BOM; the filesystem provider
  // tolerates it, so this loader must too, or the delivered skill would fail to
  // register for a reason no user could see.
  const text = String(source == null ? '' : source)
    .replace(/^\uFEFF/, '')
    .replace(/\r\n?/g, '\n');
  if (!text.startsWith('---\n')) return { front: '', body: text };
  const end = text.indexOf('\n---', 3);
  if (end === -1) return { front: '', body: text };
  const after = text.indexOf('\n', end + 4);
  const body = after === -1 ? '' : text.slice(after + 1);
  return { front: text.slice(4, end), body };
}

function unquote(raw) {
  const value = raw.trim();
  if (value.length >= 2) {
    const first = value[0];
    const last = value[value.length - 1];
    if (first === last && (first === '"' || first === "'")) return value.slice(1, -1);
  }
  return value;
}

function parseInlineList(raw) {
  const value = raw.trim();
  if (!value.startsWith('[') || !value.endsWith(']')) return undefined;
  return value
    .slice(1, -1)
    .split(',')
    .map((item) => unquote(item))
    .filter((item) => item !== '');
}

/**
 * Parse the small YAML subset the skill frontmatter uses: scalar keys, a nested
 * one-level map (metadata), inline lists, and `|` / `>` block scalars. Anything
 * else is a bug in the shipped SKILL.md, so it is reported instead of guessed.
 */
export function parseFrontmatter(front) {
  const data = {};
  const lines = String(front == null ? '' : front).split('\n');
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    index += 1;
    if (line.trim() === '' || line.trim().startsWith('#')) continue;
    const match = /^([A-Za-z0-9_-]+):(?:[ \t]+(.*))?$/.exec(line);
    if (match === null) {
      throw new Error(`project-dept: cannot parse frontmatter line "${line}"`);
    }
    const key = match[1];
    const inline = match[2] === undefined ? '' : match[2];
    if (inline === '|' || inline === '>' || inline === '|-' || inline === '>-') {
      const collected = [];
      while (index < lines.length && (lines[index].startsWith(' ') || lines[index].trim() === '')) {
        collected.push(lines[index].replace(/^ {2}/, ''));
        index += 1;
      }
      while (collected.length > 0 && collected[collected.length - 1].trim() === '') collected.pop();
      data[key] = inline.startsWith('>') ? collected.join(' ') : collected.join('\n');
      continue;
    }
    if (inline !== '') {
      const list = parseInlineList(inline);
      data[key] = list === undefined ? unquote(inline) : list;
      continue;
    }
    const nested = {};
    while (index < lines.length && /^[ \t]+\S/.test(lines[index])) {
      const inner = /^[ \t]+([A-Za-z0-9_-]+):(?:[ \t]+(.*))?$/.exec(lines[index]);
      index += 1;
      if (inner === null) continue;
      const innerRaw = inner[2] === undefined ? '' : inner[2];
      const innerList = parseInlineList(innerRaw);
      nested[inner[1]] = innerList === undefined ? unquote(innerRaw) : innerList;
    }
    data[key] = nested;
  }
  return data;
}

/** Read and validate one bundled skill. Exported so tests can drive every branch. */
export function loadSkill(dir = DEFAULT_SKILL_DIR) {
  const skillDir = resolve(dir);
  const file = join(skillDir, 'SKILL.md');
  const source = readFileSync(file, 'utf8');
  const { front, body } = splitFrontmatter(source);
  const data = parseFrontmatter(front);
  const name = String(data.name == null ? '' : data.name).trim();
  const description = String(data.description == null ? '' : data.description).trim();
  if (name === '') throw new Error(`dsh-project-dept: ${file} has no frontmatter name`);
  if (description === '') throw new Error(`dsh-project-dept: ${file} has no frontmatter description`);
  if (body.trim() === '') throw new Error(`dsh-project-dept: ${file} has no body`);
  const whenToUse = data.whenToUse === undefined || data.whenToUse === '' ? undefined : String(data.whenToUse);
  return {
    name,
    description,
    whenToUse,
    content: body.replace(/^\n+/, ''),
    path: file,
    metadata: data.metadata !== null && typeof data.metadata === 'object' && !Array.isArray(data.metadata) ? data.metadata : undefined,
    resourceBase: { kind: 'directory', path: skillDir },
  };
}

export const inject = ['skills'];

/** Load every skill the bundle carries, in declaration order. */
export function loadSkills() {
  return SKILL_NAMES.map((name) => loadSkill(skillDirOf(name)));
}

export function apply(ctx) {
  const skills = ctx.skills ?? (typeof ctx.get === 'function' ? ctx.get('skills') : undefined);
  if (skills === undefined || skills === null || typeof skills.register !== 'function') {
    throw new Error('dsh-project-dept: the skill registry (ctx.skills) is not available, so the bundled skills cannot be registered');
  }
  const definitions = loadSkills();
  const register = () => definitions.map((definition) => skills.register(definition));
  if (typeof ctx.effect === 'function') ctx.effect(register);
  else register();
}

export const __test__ = { splitFrontmatter, parseFrontmatter, loadSkill, loadSkills, skillDirOf, DEFAULT_SKILL_DIR, SKILL_NAMES };