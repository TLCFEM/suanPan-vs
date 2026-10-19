/*
 * Offline smoke test for the suanPan language framework.
 *
 * The providers depend on the `vscode` module, which is only available inside
 * the extension host.  This script installs a minimal stub, loads the compiled
 * `out/` modules and exercises the parser, indexer and providers directly so
 * the framework can be validated without launching VS Code.
 *
 * Usage:  npm run compile && node scripts/smoke.js
 */
'use strict';

const assert = require('assert');
const Module = require('module');
const path = require('path');

// ---------------------------------------------------------------------------
// minimal `vscode` stub
// ---------------------------------------------------------------------------

const pos = (line, character) => ({ line, character });

class Range {
	constructor(sl, sc, el, ec) {
		this.start = pos(sl, sc);
		this.end = pos(el, ec);
	}
	contains(p) {
		return (
			(this.start.line < p.line || (this.start.line === p.line && this.start.character <= p.character)) &&
			(p.line < this.end.line || (p.line === this.end.line && p.character <= this.end.character))
		);
	}
}

class MarkdownString {
	constructor() { this.value = ''; }
	appendMarkdown(value) { this.value += value; return this; }
	appendCodeblock(value) { this.value += '\n```\n' + value + '\n```'; return this; }
}

const providers = { hover: [], completion: [], signature: [], symbols: [], definition: [] };
const register = bucket => (_selector, provider) => { bucket.push(provider); return { dispose() {} }; };

const vscode = {
	Range,
	Position: class Position { constructor(line, character) { Object.assign(this, pos(line, character)); } },
	DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
	Diagnostic: class Diagnostic { constructor(range, message, severity) { Object.assign(this, { range, message, severity }); } },
	MarkdownString,
	Hover: class Hover { constructor(contents, range) { Object.assign(this, { contents, range }); } },
	CompletionItem: class CompletionItem { constructor(label, kind) { Object.assign(this, { label, kind }); } },
	CompletionItemKind: { Module: 0, Keyword: 1, Class: 2, Property: 3, EnumMember: 4, Value: 5, Reference: 6, Variable: 7 },
	SignatureHelp: class SignatureHelp { constructor() { this.signatures = []; this.activeSignature = 0; this.activeParameter = 0; } },
	SignatureInformation: class SignatureInformation { constructor(label) { this.label = label; this.parameters = []; } },
	ParameterInformation: class ParameterInformation { constructor(label, documentation) { Object.assign(this, { label, documentation }); } },
	DocumentSymbol: class DocumentSymbol { constructor(name, detail, kind, range, selectionRange) { Object.assign(this, { name, detail, kind, range, selectionRange }); } },
	SymbolKind: { Object: 0, Constant: 1 },
	Location: class Location { constructor(uri, range) { Object.assign(this, { uri, range }); } },
	Uri: { joinPath: (base, ...rest) => ({ fsPath: path.join(base.fsPath || '', ...rest) }) },
	languages: {
		createDiagnosticCollection: () => ({ set() {}, delete() {}, dispose() {} }),
		registerHoverProvider: register(providers.hover),
		registerCompletionItemProvider: register(providers.completion),
		registerSignatureHelpProvider: register(providers.signature),
		registerDocumentSymbolProvider: register(providers.symbols),
		registerDefinitionProvider: register(providers.definition)
	},
	workspace: {
		onDidOpenTextDocument: () => ({ dispose() {} }),
		onDidChangeTextDocument: () => ({ dispose() {} }),
		onDidCloseTextDocument: () => ({ dispose() {} }),
		onDidSaveTextDocument: () => ({ dispose() {} }),
		textDocuments: []
	},
	window: {}
};

const originalLoad = Module._load;
Module._load = function (request) {
	if (request === 'vscode') return vscode;
	return originalLoad.apply(this, arguments);
};

// ---------------------------------------------------------------------------
// harness
// ---------------------------------------------------------------------------

const root = path.resolve(__dirname, '..');
const out = path.join(root, 'out');

const { Registry } = require(path.join(out, 'schema.js'));
const { buildIndex } = require(path.join(out, 'indexer.js'));
const { parseDocument } = require(path.join(out, 'parser.js'));
const { registerLanguageFeatures } = require(path.join(out, 'providers.js'));

let checks = 0;
const check = (label, condition) => {
	checks++;
	if (!condition) throw new Error(`FAIL: ${label}`);
	console.log(`  ok  ${label}`);
};

const registry = Registry.fromFile(path.join(root, 'syntaxes', 'commands.json'));

const text = [
	'variable E 132',
	'node 1 0 0',
	'node 2 1 0',
	'material Elastic1D 1 $E',
	'element EB21 1 1 2 7.2 6.8 1 \\',
	'  no',
	'fix 1 E 1',
	'cload 1 0 23 2 2',
	'set system_solver LAPACK',
	'unknown_command hello',
	'element Nope 9 1 2 1 1 1',
	'element EB21 1 2 1 1 1 1'
];

const document = {
	uri: { toString: () => 'smoke.sp', fsPath: 'smoke.sp' },
	languageId: 'suanPan',
	version: 1,
	lineCount: text.length,
	lineAt: i => ({ text: text[i] })
};

console.log('parser');
const lines = parseDocument(document);
check('logical lines are formed', lines.length > 0);
check(
	'backslash continuation joins lines',
	lines[4].tokens.map(t => t.text).join(' ') === 'element EB21 1 1 2 7.2 6.8 1 no'
);
check('inline comment is stripped', lines.every(l => !l.tokens.some(t => t.text.startsWith('!'))));

console.log('indexer');
const index = buildIndex(document, registry);
check('nodes are indexed', (index.byCategoryTag.get('node') || new Map()).size === 2);
check('materials are indexed', index.byCategoryTag.get('material').get(1).type === 'Elastic1D');
check('elements are indexed', index.byCategoryTag.get('element').get(1).type === 'EB21');
check('constraints are indexed', index.byCategoryTag.get('constraint').get(1) !== undefined);
check('loads are indexed', index.byCategoryTag.get('load').get(1) !== undefined);
check('variables are indexed', index.variables.get('E').value === '132');
check('unknown command is reported', index.issues.some(i => /unknown_command/.test(i.message)));
check('unknown type is reported', index.issues.some(i => /Unknown element type 'Nope'/.test(i.message)));
check('duplicate tags are reported', index.issues.some(i => /Duplicate element tag 1/.test(i.message)));

console.log('providers');
const context = { subscriptions: [], extensionUri: { fsPath: root } };
registerLanguageFeatures(context, registry);

const hoverMaterial = providers.hover[0].provideHover(document, pos(3, 2));
check('hover on category keyword', hoverMaterial && /material/.test(hoverMaterial.contents.value));
const hoverType = providers.hover[0].provideHover(document, pos(3, 11));
check('hover on object type', hoverType && /Uniaxial Elastic Material/.test(hoverType.contents.value));
const hoverVar = providers.hover[0].provideHover(document, pos(3, 21));
check('hover on variable reference', hoverVar && /132/.test(hoverVar.contents.value));

const start = providers.completion[0].provideCompletionItems(document, pos(0, 0));
check('completion offers categories and commands', start.some(i => i.label === 'element') && start.some(i => i.label === 'variable'));
const types = providers.completion[0].provideCompletionItems(document, pos(3, 10));
check('completion offers types of the category', types.some(i => i.label === 'Elastic1D'));
const dofs = providers.completion[0].provideCompletionItems(document, pos(6, 6));
check('completion offers DoF identifiers', dofs.some(i => i.label === 'E'));
const tags = providers.completion[0].provideCompletionItems(document, pos(7, 15));
check('completion offers object tags', tags.some(i => i.label === '1'));
const properties = providers.completion[0].provideCompletionItems(document, pos(8, 5));
check('completion after set offers properties', properties.some(i => i.label === 'system_solver'));
const enums = providers.completion[0].provideCompletionItems(document, pos(8, 18));
check('completion offers enumerated options', enums.some(i => i.label === 'LAPACK'));

const signature = providers.signature[0].provideSignatureHelp(document, pos(4, 30));
check('signature help describes the element form', signature && /EB21/.test(signature.signatures[0].label));

const symbols = providers.symbols[0].provideDocumentSymbols(document);
check('document symbols include objects and variables', symbols.some(s => s.name === 'Elastic1D 1') && symbols.some(s => s.name === '$E'));

const definition = providers.definition[0].provideDefinition(document, pos(4, 17));
check('go-to-definition resolves a node tag', definition && definition.range.start.line === 2);
const variableDefinition = providers.definition[0].provideDefinition(document, pos(3, 21));
check('go-to-definition resolves a variable', variableDefinition && variableDefinition.range.start.line === 0);

console.log(`\n${checks} checks passed.`);
