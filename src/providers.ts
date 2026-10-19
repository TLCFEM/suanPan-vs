import * as vscode from 'vscode';
import { Entry, Form, Param, Registry } from './schema';
import {
	buildIndex,
	ModelIndex,
	ObjectDecl,
	referenceCategory,
	resolveShape,
	Shape
} from './indexer';
import { lineAt, LogicalLine, tokenAt, Token } from './parser';

const LANGUAGE = 'suanPan';
const INTEGER_RE = /^[+-]?\d+$/;

/**
 * Instantiate the language features on top of the generated schema and register
 * them with VS Code. Returns the diagnostic collection for disposal.
 */
export function registerLanguageFeatures(context: vscode.ExtensionContext, registry: Registry): void {
	const indexCache = new Map<string, { version: number; index: ModelIndex }>();

	const getIndex = (document: vscode.TextDocument): ModelIndex => {
		const key = document.uri.toString();
		const cached = indexCache.get(key);
		if (cached && cached.version === document.version) return cached.index;
		const index = buildIndex(document, registry);
		indexCache.set(key, { version: document.version, index });
		return index;
	};

	// ---------------------------------------------------------------- diagnostics
	const diagnostics = vscode.languages.createDiagnosticCollection('suanPan');
	context.subscriptions.push(diagnostics);

	const refresh = (document: vscode.TextDocument): void => {
		if (document.languageId !== LANGUAGE) return;
		const index = getIndex(document);
		diagnostics.set(
			document.uri,
			index.issues.map(i => {
				const diagnostic = new vscode.Diagnostic(i.range, i.message, i.severity);
				diagnostic.source = i.source;
				return diagnostic;
			})
		);
	};

	let timer: NodeJS.Timeout | undefined;
	const schedule = (document: vscode.TextDocument): void => {
		if (document.languageId !== LANGUAGE) return;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => refresh(document), 300);
	};

	context.subscriptions.push(
		vscode.workspace.onDidOpenTextDocument(document => refresh(document)),
		vscode.workspace.onDidChangeTextDocument(event => schedule(event.document)),
		vscode.workspace.onDidCloseTextDocument(document => {
			diagnostics.delete(document.uri);
			indexCache.delete(document.uri.toString());
		}),
		vscode.workspace.onDidSaveTextDocument(document => refresh(document))
	);

	for (const document of vscode.workspace.textDocuments) refresh(document);

	// ---------------------------------------------------------------- hover
	context.subscriptions.push(
		vscode.languages.registerHoverProvider(LANGUAGE, {
			provideHover(document, position) {
				return provideHover(getIndex(document), position);
			}
		})
	);

	// ---------------------------------------------------------------- completion
	context.subscriptions.push(
		vscode.languages.registerCompletionItemProvider(LANGUAGE, {
			provideCompletionItems(document, position) {
				return provideCompletion(getIndex(document), position);
			}
		}, '$')
	);

	// ---------------------------------------------------------------- signature help
	context.subscriptions.push(
		vscode.languages.registerSignatureHelpProvider(LANGUAGE, {
			provideSignatureHelp(document, position) {
				return provideSignature(getIndex(document), position);
			}
		}, ' ', ',')
	);

	// ---------------------------------------------------------------- document symbols
	context.subscriptions.push(
		vscode.languages.registerDocumentSymbolProvider(LANGUAGE, {
			provideDocumentSymbols(document) {
				return provideSymbols(getIndex(document));
			}
		})
	);

	// ---------------------------------------------------------------- definition
	context.subscriptions.push(
		vscode.languages.registerDefinitionProvider(LANGUAGE, {
			provideDefinition(document, position) {
				return provideDefinition(getIndex(document), position);
			}
		})
	);
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function docUri(entry: Entry): vscode.MarkdownString {
	const md = new vscode.MarkdownString();
	md.appendMarkdown(`**${entry.name}**`);
	if (entry.category) md.appendMarkdown(` *(${entry.category})*`);
	if (entry.summary) md.appendMarkdown(`\n\n${entry.summary}`);
	for (const form of entry.forms) md.appendCodeblock(form.syntax, 'suanpan');
	return md;
}

function findEntry(registry: Registry, index: ModelIndex, line: LogicalLine, token: Token): Entry | undefined {
	const position = line.tokens.indexOf(token);
	if (position === 0) {
		const command = registry.findCommand(token.text.toLowerCase());
		if (command) return command;
	}
	if (position === 1) {
		const first = line.tokens[0].text.toLowerCase();
		if (registry.isCategory(first)) {
			const type = registry.findTypeInCategory(first, token.text);
			if (type) return type;
		}
	}
	return registry.findType(token.text) ?? registry.findCommand(token.text.toLowerCase());
}

function provideHover(index: ModelIndex, position: vscode.Position): vscode.Hover | undefined {
	const line = lineAt(index.lines, position);
	if (!line) return undefined;
	const token = tokenAt(index.lines, position);
	if (!token) return undefined;

	// variable reference
	const ref = index.refs.find(r => r.token === token);
	if (ref) {
		const declaration = index.variables.get(ref.name);
		const md = new vscode.MarkdownString();
		md.appendMarkdown(`**$${ref.name}**`);
		if (declaration) {
			md.appendMarkdown(`\n\nValue: \`${declaration.value}\``);
			md.appendMarkdown(`\n\nDefined on line ${declaration.token.line + 1}.`);
		} else {
			md.appendMarkdown('\n\n(Variable is not defined in this file.)');
		}
		return new vscode.Hover(md, token.range);
	}

	// object category keyword, e.g. `material`, `element`
	const tokenPosition = line.tokens.indexOf(token);
	if (tokenPosition === 0 && index.registry.isCategory(token.text.toLowerCase())) {
		const category = token.text.toLowerCase();
		const info = index.registry.schema.categories[category];
		const md = new vscode.MarkdownString();
		md.appendMarkdown(`**${category}**`);
		if (info) md.appendMarkdown(`\n\n${info.description}`);
		md.appendMarkdown(`\n\n${index.registry.typesOfCategory(category).length} object types available.`);
		return new vscode.Hover(md, token.range);
	}

	const entry = findEntry(index.registry, index, line, token);
	if (entry) return new vscode.Hover(docUri(entry), token.range);

	// DoF / output token vocabulary
	const lower = token.text.toLowerCase();
	if (index.registry.schema.dofTokens.some(d => d.toLowerCase() === lower)) {
		return new vscode.Hover(markdown(`suanPan DoF identifier \`${token.text}\``), token.range);
	}
	if (index.registry.schema.outputTokens.some(d => d.toLowerCase() === lower)) {
		return new vscode.Hover(markdown(`suanPan response/output token \`${token.text}\``), token.range);
	}

	return undefined;
}

function markdown(text: string): vscode.MarkdownString {
	const md = new vscode.MarkdownString();
	md.appendMarkdown(text);
	return md;
}

function tokensBefore(line: LogicalLine, position: vscode.Position): Token[] {
	return line.tokens.filter(t =>
		t.line < position.line || (t.line === position.line && t.character + t.length <= position.character)
	);
}

function provideCompletion(index: ModelIndex, position: vscode.Position): vscode.CompletionItem[] {
	const items: vscode.CompletionItem[] = [];
	const registry = index.registry;
	const line = lineAt(index.lines, position);

	if (!line || line.tokens.length === 0) {
		addCommandCompletions(registry, items);
		return items;
	}

	const before = tokensBefore(line, position);
	if (before.length === 0) {
		addCommandCompletions(registry, items);
		return items;
	}

	const first = before[0].text.toLowerCase();

	// completing the object type: `material <here>`
	if (before.length === 1 && registry.isCategory(first)) {
		for (const entry of registry.typesOfCategory(first)) {
			items.push(typeCompletion(entry));
		}
		return items;
	}

	// completing a `set` property
	if (first === 'set' && before.length === 1) {
		const setEntry = registry.findCommand('set');
		const seen = new Set<string>();
		for (const form of setEntry?.forms ?? []) {
			const name = form.syntax.split(/\s+/)[1];
			if (name && !seen.has(name)) {
				seen.add(name);
				const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Property);
				item.detail = 'set property';
				item.documentation = markdown(form.params.map(p => p.description).join(' '));
				items.push(item);
			}
		}
		return items;
	}

	// completing an enum value: `set system_solver <here>`
	if (first === 'set' && before.length === 2) {
		const property = before[1].text.toLowerCase();
		const options = registry.schema.enumOptions[property];
		if (options) {
			for (const option of options) {
				items.push(new vscode.CompletionItem(option, vscode.CompletionItemKind.EnumMember));
			}
		}
		return items;
	}

	// argument-position completions (DoF tokens, tags, booleans)
	const shape = resolveShape(registry, line);
	if (shape && shape.form) {
		const provided = before.length - shape.base;
		const param = paramAt(shape.form, provided + 1);
		if (param) {
			if (/dof/i.test(param.description)) {
				for (const dof of registry.schema.dofTokens) {
					const item = new vscode.CompletionItem(dof, vscode.CompletionItemKind.EnumMember);
					item.detail = 'DoF identifier';
					items.push(item);
				}
				return items;
			}
			if (param.type === 'boolean') {
				for (const value of ['true', 'false']) {
					items.push(new vscode.CompletionItem(value, vscode.CompletionItemKind.Value));
				}
				return items;
			}
			const category = referenceCategory(param);
			if (category) {
				const bucket = index.byCategoryTag.get(category);
				if (bucket) {
					for (const decl of bucket.values()) {
						const item = new vscode.CompletionItem(String(decl.tag), vscode.CompletionItemKind.Reference);
						item.detail = `${decl.type} (${category} tag ${decl.tag})`;
						item.documentation = markdown(`${decl.type} defined on line ${decl.tagToken.line + 1}.`);
						items.push(item);
					}
				}
				return items;
			}
		}
	}

	// variable references
	if (index.variables.size > 0 && position.character > 0) {
		const prefix = index.document.lineAt(position.line).text.slice(0, position.character);
		if (prefix.endsWith('$') || /[^\w]\$$/.test(prefix)) {
			for (const [name, variable] of index.variables) {
				const item = new vscode.CompletionItem(`$${name}`, vscode.CompletionItemKind.Variable);
				item.detail = variable.value;
				items.push(item);
			}
		}
	}

	return items;
}

function addCommandCompletions(registry: Registry, items: vscode.CompletionItem[]): void {
	// category keywords first, then remaining commands
	for (const category of registry.categoryKeys()) {
		const info = registry.schema.categories[category];
		const item = new vscode.CompletionItem(category, vscode.CompletionItemKind.Module);
		item.detail = info?.description ?? 'object category';
		items.push(item);
	}
	for (const entry of registry.commandEntries()) {
		if (registry.isCategory(entry.name.toLowerCase())) continue;
		const item = new vscode.CompletionItem(entry.name, vscode.CompletionItemKind.Keyword);
		item.documentation = docUri(entry);
		items.push(item);
	}
}

function typeCompletion(entry: Entry): vscode.CompletionItem {
	const item = new vscode.CompletionItem(entry.name, vscode.CompletionItemKind.Class);
	item.detail = entry.category ?? 'type';
	item.documentation = docUri(entry);
	return item;
}

function paramAt(form: Form, index: number): Param | undefined {
	for (const param of form.params) {
		const end = param.end ?? (param.variadic ? Number.POSITIVE_INFINITY : param.index);
		if (index >= param.index && index <= end) return param;
	}
	return undefined;
}

function provideSignature(index: ModelIndex, position: vscode.Position): vscode.SignatureHelp | undefined {
	const line = lineAt(index.lines, position);
	if (!line) return undefined;
	const shape = resolveShape(index.registry, line);
	if (!shape || !shape.entry || !shape.form) return undefined;
	const form = shape.form;

	const before = tokensBefore(line, position);
	const provided = Math.max(0, before.length - shape.base + 1);

	const help = new vscode.SignatureHelp();
	for (const form of shape.entry.forms) {
		const signature = new vscode.SignatureInformation(form.syntax);
		signature.parameters = form.params.map(p => new vscode.ParameterInformation(
			`${p.required ? '(' : '['}${p.index}${p.variadic ? '...' : ''}${p.required ? ')' : ']'}`,
			new vscode.MarkdownString(`${p.type}, ${p.description}${p.default !== undefined ? ` (default: ${p.default})` : ''}`)
		));
		help.signatures.push(signature);
	}
	help.activeSignature = Math.max(0, shape.entry.forms.findIndex(f => f === form));
	help.activeParameter = Math.max(0, Math.min(provided - 1, form.params.length - 1));
	return help;
}

function provideSymbols(index: ModelIndex): vscode.DocumentSymbol[] {
	const symbols: vscode.DocumentSymbol[] = [];

	for (const variable of index.variables.values()) {
		symbols.push(new vscode.DocumentSymbol(
			`$${variable.name}`,
			variable.value,
			vscode.SymbolKind.Constant,
			variable.token.range,
			variable.token.range
		));
	}

	for (const object of index.objects) {
		const selection = object.tagToken.range;
		symbols.push(new vscode.DocumentSymbol(
			`${object.type} ${object.tag}`,
			object.category,
			vscode.SymbolKind.Object,
			selection,
			selection
		));
	}

	symbols.sort((a, b) =>
		a.range.start.line - b.range.start.line
		|| a.range.start.character - b.range.start.character
	);
	return symbols;
}

function provideDefinition(index: ModelIndex, position: vscode.Position): vscode.Definition | undefined {
	const line = lineAt(index.lines, position);
	const token = tokenAt(index.lines, position);
	if (!line || !token) return undefined;

	// $variable -> declaration
	const ref = index.refs.find(r => r.token === token);
	if (ref) {
		const declaration = index.variables.get(ref.name);
		if (declaration) return new vscode.Location(index.document.uri, declaration.token.range);
	}

	// integer tag argument -> object declaration
	const shape = resolveShape(index.registry, line);
	if (!shape || !shape.form) return undefined;
	const positionInLine = line.tokens.indexOf(token);
	if (positionInLine < shape.base) return undefined;

	const provided = positionInLine - shape.base + 1;
	const param = paramAt(shape.form, provided);
	if (!param) return undefined;
	const category = referenceCategory(param);
	if (!category) return undefined;

	const text = token.text;
	if (!INTEGER_RE.test(text)) return undefined;
	const decl = index.byCategoryTag.get(category)?.get(Number(text));
	if (decl) return new vscode.Location(index.document.uri, decl.tagToken.range);
	return undefined;
}

export { ObjectDecl, Shape };
