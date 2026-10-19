import * as vscode from 'vscode';
import { Entry, Form, Param, Registry } from './schema';
import { LogicalLine, parseDocument, Token } from './parser';

export interface ObjectDecl {
	category: string;
	type: string;
	entry: Entry;
	tag: number;
	tagToken: Token;
	line: LogicalLine;
}

export interface VariableDecl {
	name: string;
	value: string;
	token: Token;
}

export interface VariableRef {
	name: string;
	token: Token;
}

export interface Issue {
	message: string;
	range: vscode.Range;
	severity: vscode.DiagnosticSeverity;
	source: string;
}

export interface ModelIndex {
	document: vscode.TextDocument;
	registry: Registry;
	lines: LogicalLine[];
	objects: ObjectDecl[];
	byCategoryTag: Map<string, Map<number, ObjectDecl>>;
	variables: Map<string, VariableDecl>;
	refs: VariableRef[];
	issues: Issue[];
}

/**
 * Commands that are always valid even if the manual does not carry a syntax
 * block for them. Mirrors the dispatch table in `Toolbox/command.cpp`.
 */
const BUILTIN_COMMANDS = new Set<string>([
	'exit', 'quit', 'overview', 'file', 'var', 'variable', 'domain',
	'enable', 'disable', 'mute', 'erase', 'delete', 'remove', 'list',
	'protect', 'save', 'set', 'suspend', 'use', 'command', 'example',
	'precheck', 'analyze', 'analyse', 'fullname', 'pwd', 'sleep', 'benchmark',
	'clear', 'reset', 'summary', 'terminal', 't', 'upsampling',
	'response_spectrum', 'sdof_response', 'license', 'version', 'plot', 'peek',
	'qrcode', 'help', 'node'
]);

const INTEGER_RE = /^[+-]?\d+$/;
const NUMBER_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eEdDfF][+-]?\d+)?$/;
const VARIABLE_RE = /\$([A-Za-z0-9_]+)/g;

export function buildIndex(document: vscode.TextDocument, registry: Registry): ModelIndex {
	const lines = parseDocument(document);
	const index: ModelIndex = {
		document,
		registry,
		lines,
		objects: [],
		byCategoryTag: new Map(),
		variables: new Map(),
		refs: [],
		issues: []
	};

	for (const line of lines) {
		analyseLine(index, line);
	}

	return index;
}

/** Resolved interpretation of a logical line. */
export interface Shape {
	keyword: string;
	category?: string;
	objectType?: string;
	entry?: Entry;
	form?: Form;
	/** number of leading tokens taken by the keyword (and object type) */
	base: number;
}

export function resolveShape(registry: Registry, line: LogicalLine): Shape | undefined {
	if (line.tokens.length === 0) return undefined;
	const keyword = line.tokens[0].text.toLowerCase();

	let category: string | undefined;
	let objectType: string | undefined;
	let entry: Entry | undefined;
	let base = 1;

	if (registry.isCategory(keyword)) {
		category = keyword;
		const candidate = line.tokens[1];
		if (candidate && /^[A-Za-z][A-Za-z0-9_-]*$/.test(candidate.text)) {
			objectType = candidate.text;
			entry = registry.findTypeInCategory(keyword, candidate.text);
			base = 2;
		}
	} else {
		entry = registry.findCommand(keyword);
		category = registry.categoryOfCommand(keyword);
	}

	const form = entry ? bestForm(entry, line.tokens.length - base) : undefined;
	return { keyword, category, objectType, entry, form, base };
}

/** Pick the form whose arity best matches the number of supplied arguments. */
function bestForm(entry: Entry, provided: number): Form | undefined {
	let best: Form | undefined;
	let bestScore = Number.POSITIVE_INFINITY;
	for (const form of entry.forms) {
		const min = minimumArguments(form);
		if (provided < min) {
			const score = min - provided;
			if (score < bestScore) {
				bestScore = score;
				best = form;
			}
		} else {
			return form;
		}
	}
	return best ?? entry.forms[0];
}

function minimumArguments(form: Form): number {
	let min = 0;
	for (const param of form.params) {
		if (!param.required) continue;
		const end = param.end ?? param.index;
		min = Math.max(min, end);
	}
	return min;
}

function argumentToken(line: LogicalLine, base: number, param: Param): Token | undefined {
	// parameter indices are 1-based and follow the type token
	const tokenIndex = base + param.index - 1;
	return line.tokens[tokenIndex];
}

function findTagParam(form: Form | undefined): Param | undefined {
	if (!form) return undefined;
	return form.params.find(p => p.type === 'integer' && /unique/i.test(p.description) && /tag/i.test(p.description))
		?? form.params.find(p => p.type === 'integer' && /tag/i.test(p.description));
}

function analyseLine(index: ModelIndex, line: LogicalLine): void {
	const shape = resolveShape(index.registry, line);
	if (!shape) return;

	// variable definitions -------------------------------------------------
	if (shape.keyword === 'var' || shape.keyword === 'variable') {
		const name = line.tokens[1];
		if (name) {
			const value = line.tokens.slice(2).map(t => t.text).join(' ');
			index.variables.set(name.text, { name: name.text, value, token: name });
		}
		return;
	}

	// variable references --------------------------------------------------
	for (const token of line.tokens) {
		VARIABLE_RE.lastIndex = 0;
		let match: RegExpExecArray | null;
		while ((match = VARIABLE_RE.exec(token.text)) !== null) {
			index.refs.push({ name: match[1], token });
		}
	}

	// unknown command ------------------------------------------------------
	const known = index.registry.findCommand(shape.keyword) !== undefined
		|| index.registry.isCategory(shape.keyword)
		|| index.registry.categoryOfCommand(shape.keyword) !== undefined
		|| BUILTIN_COMMANDS.has(shape.keyword);

	if (!known) {
		const token = line.tokens[0];
		index.issues.push(issue(`Unknown command '${token.text}'.`, token, vscode.DiagnosticSeverity.Warning));
		return;
	}

	// unknown object type --------------------------------------------------
	if (shape.category && shape.objectType && !shape.entry) {
		const token = line.tokens[1];
		index.issues.push(issue(
			`Unknown ${shape.category} type '${token.text}'. It may be provided by an external module.`,
			token,
			vscode.DiagnosticSeverity.Warning
		));
	}

	// argument count -------------------------------------------------------
	if (shape.entry && shape.form) {
		const provided = line.tokens.length - shape.base;
		const min = minimumArguments(shape.form);
		if (provided < min) {
			const last = line.tokens[line.tokens.length - 1];
			index.issues.push(issue(
				`'${shape.entry.name}' expects at least ${min} argument${min === 1 ? '' : 's'}, but ${provided} ${provided === 1 ? 'was' : 'were'} given.`,
				last,
				vscode.DiagnosticSeverity.Warning
			));
		}
	}

	// per-argument validation ---------------------------------------------
	if (shape.form) {
		validateArguments(index, line, shape, shape.form);
	}

	// register object ------------------------------------------------------
	if (shape.category && shape.entry) {
		const param = findTagParam(shape.form);
		const token = param ? argumentToken(line, shape.base, param) : undefined;
		const tag = token && INTEGER_RE.test(token.text) ? Number(token.text) : undefined;
		if (tag !== undefined && token) {
			const decl: ObjectDecl = {
				category: shape.category,
				type: shape.entry.name,
				entry: shape.entry,
				tag,
				tagToken: token,
				line
			};
			index.objects.push(decl);
			let bucket = index.byCategoryTag.get(shape.category);
			if (!bucket) {
				bucket = new Map();
				index.byCategoryTag.set(shape.category, bucket);
			}
			const existing = bucket.get(tag);
			if (existing) {
				index.issues.push(issue(
					`Duplicate ${shape.category} tag ${tag}; first defined on line ${existing.tagToken.line + 1}.`,
					token,
					vscode.DiagnosticSeverity.Warning
				));
			} else {
				bucket.set(tag, decl);
			}
		}
	}
}

function validateArguments(index: ModelIndex, line: LogicalLine, shape: Shape, form: Form): void {
	for (const param of form.params) {
		const token = argumentToken(line, shape.base, param);
		if (!token) continue;

		if (/dof/i.test(param.description)) {
			if (isVariable(token.text)) continue;
			const known = index.registry.schema.dofTokens.some(d => d.toLowerCase() === token.text.toLowerCase());
			if (!known) {
				index.issues.push(issue(`Unknown DoF identifier '${token.text}'.`, token, vscode.DiagnosticSeverity.Warning));
			}
		} else if (param.type === 'integer' && /tag/i.test(param.description)) {
			if (isVariable(token.text) || INTEGER_RE.test(token.text)) continue;
			index.issues.push(issue(`Expected an integer tag, got '${token.text}'.`, token, vscode.DiagnosticSeverity.Warning));
		} else if (param.type === 'number' && /magnitude|modulus|coordinate|ratio|stress|angle|length|time|scale/i.test(param.description)) {
			if (isVariable(token.text) || NUMBER_RE.test(token.text)) continue;
			index.issues.push(issue(`Expected a number, got '${token.text}'.`, token, vscode.DiagnosticSeverity.Warning));
		}
	}
}

function isVariable(text: string): boolean {
	return text.includes('$');
}

export function issue(message: string, token: Token, severity: vscode.DiagnosticSeverity): Issue {
	return { message, range: token.range, severity, source: 'suanPan' };
}

/**
 * Map a parameter description to the object category a numeric argument
 * refers to, for go-to-definition and find-references.
 */
export function referenceCategory(param: Param): string | undefined {
	const text = param.description.toLowerCase();
	if (text.includes('node')) return 'node';
	if (text.includes('element')) return 'element';
	if (text.includes('material')) return 'material';
	if (text.includes('section')) return 'section';
	if (text.includes('amplitude')) return 'amplitude';
	if (text.includes('group')) return 'group';
	return undefined;
}

export { parseDocument };
