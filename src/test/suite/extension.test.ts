import * as assert from 'assert';
import * as path from 'path';

import { CommandDatabase, CommandInfo, TYPED_CATEGORIES } from '../../core/database';
import { buildModel, findSymbol, referenceAt, symbolsOf, tagTokenIndex } from '../../core/model';
import { parseDocument, statementAt, tokenAt, tokenIndex } from '../../core/parser';
import { SnippetEntry } from '../../core/snippets';

const root = path.resolve(__dirname, '../../..');

const GENERATOR_COMMANDS = new Set(['generate', 'generatebyrule', 'generatebypoint', 'generatebyplane']);
const SPECIAL_TAG_COMMANDS = new Set(['node', 'domain', 'mass', 'recorder', 'hdf5recorder', 'plainrecorder']);
const OBJECT_TYPES = [
    'node',
    'element',
    'material',
    'section',
    'constraint',
    'load',
    'amplitude',
    'expression',
    'group',
    'step',
    'solver',
    'integrator',
    'converger',
    'criterion',
    'recorder',
    'modifier',
    'interaction',
];
const OBJECT_COMMANDS = ['peek', 'delete', 'erase', 'remove', 'enable', 'disable', 'mute', 'protect', 'suspend'];

/**
 * Build a syntactically complete statement that defines an object of the
 * command's category.  Management commands (`peek`, `set`, ...) and
 * commands without object tags return `undefined`.
 */
function definitionFor(command: CommandInfo): string | undefined {
    if (!command.category) return undefined;
    // Initial conditions describe a state mutation and carry no object tag.
    if (command.name === 'initial') return undefined;
    if (SPECIAL_TAG_COMMANDS.has(command.name)) {
        if (command.name === 'recorder') return 'recorder 1 plain Node U 1';
        if (command.name === 'hdf5recorder') return 'hdf5recorder 1 Node U 1';
        if (command.name === 'plainrecorder') return 'plainrecorder 1 Node U 1';
        if (command.name === 'domain') return 'domain 1 0 0 1 1';
        return `${command.name} 1`;
    }
    if (command.name !== command.category) {
        // Shorthand commands name the type themselves; generators insert an
        // extra `nodegroup` token before the tag.
        return GENERATOR_COMMANDS.has(command.name)
            ? `${command.name} nodegroup 1 1`
            : `${command.name} 1`;
    }
    if (!command.types?.length) return undefined;
    const type = command.types[0].name;
    if (command.category === 'group' && GENERATOR_COMMANDS.has(type)) {
        return `group ${type} nodegroup 1 1`;
    }
    return `${command.name} ${type} 1`;
}

suite('suanPan parser', () => {
    test('ignores comment lines and inline comments', () => {
        const parsed = parseDocument(['# comment', '! also a comment', 'node 1 2 3 ! tail'].join('\n'));
        assert.strictEqual(parsed.statements.length, 1);
        assert.strictEqual(parsed.statements[0].text, 'node 1 2 3');
    });

    test('treats commas and tabs as delimiters', () => {
        const parsed = parseDocument('node,1,\t2,3');
        assert.deepStrictEqual(
            parsed.statements[0].tokens.map(token => token.value),
            ['node', '1', '2', '3']
        );
    });

    test('joins continued lines', () => {
        const parsed = parseDocument(['node 1 2 3 \\', '4 5 6'].join('\n'));
        assert.strictEqual(parsed.statements.length, 1);
        assert.strictEqual(parsed.statements[0].text, 'node 1 2 3 4 5 6');
        assert.strictEqual(parsed.statements[0].line, 0);
        assert.strictEqual(parsed.statements[0].endLine, 1);
    });

    test('reports a dangling continuation', () => {
        const parsed = parseDocument('node 1 2 3 \\');
        assert.strictEqual(parsed.danglingContinuation, 0);
    });

    test('tracks the original token positions', () => {
        const parsed = parseDocument('element T2D2 7 1 2 3');
        const token = parsed.statements[0].tokens[2];
        assert.strictEqual(token.value, '7');
        assert.strictEqual(token.line, 0);
        assert.strictEqual(token.start, 13);
    });

    test('handles empty and comment-only documents', () => {
        const empty = parseDocument('');
        assert.deepStrictEqual(empty.statements, []);
        assert.deepStrictEqual(empty.commentLines, []);

        const comments = parseDocument(['  # first', '\t# second', '! bang', '   '].join('\n'));
        assert.deepStrictEqual(comments.statements, []);
        assert.deepStrictEqual(comments.commentLines, [0, 1, 2]);
    });

    test('strips a UTF-8 byte order mark without shifting columns', () => {
        const parsed = parseDocument('node 1 2 3'.replace('node', '\ufeffnode'));
        const statement = parsed.statements[0];
        assert.strictEqual(statement.text, 'node 1 2 3');
        assert.strictEqual(statement.tokens[0].value, 'node');
        assert.strictEqual(statement.tokens[0].start, 1);
    });

    test('reports a dangling continuation even without a partial token', () => {
        const parsed = parseDocument(['node 1 0 0', '\\'].join('\n'));
        assert.deepStrictEqual(
            parsed.statements.map(statement => statement.text),
            ['node 1 0 0']
        );
        assert.strictEqual(parsed.danglingContinuation, 1);
    });

    test('keeps a continuation across comment and blank lines', () => {
        const parsed = parseDocument(['node 1 2 \\', '# comment', '', '3 4'].join('\n'));
        assert.strictEqual(parsed.statements.length, 1);
        assert.strictEqual(parsed.statements[0].text, 'node 1 2 3 4');
        assert.strictEqual(parsed.statements[0].endLine, 3);
    });

    test('allows an inline comment after a continuation marker', () => {
        const parsed = parseDocument('node 1 2 \\ ! trailing comment\n3');
        assert.strictEqual(parsed.statements[0].text, 'node 1 2 3');
    });

    test('accepts CRLF and bare carriage return line endings', () => {
        const parsed = parseDocument('node 1 0 0\r\nnode 2 1 0\rnode 3 2 0');
        assert.deepStrictEqual(
            parsed.statements.map(statement => statement.text),
            ['node 1 0 0', 'node 2 1 0', 'node 3 2 0']
        );
    });

    test('keeps the original spelling but lower cases the verb', () => {
        const parsed = parseDocument('ELEMENT, T2D2,\t7, 1, 2');
        const statement = parsed.statements[0];
        assert.strictEqual(statement.verb, 'element');
        assert.strictEqual(statement.text, 'ELEMENT T2D2 7 1 2');
        assert.deepStrictEqual(
            statement.tokens.map(token => [token.value, token.line, token.start]),
            [
                ['ELEMENT', 0, 0],
                ['T2D2', 0, 9],
                ['7', 0, 15],
                ['1', 0, 18],
                ['2', 0, 21],
            ]
        );
    });

    test('lets a continued token span two source lines', () => {
        // Without a space before the backslash the two pieces form one token.
        const statement = parseDocument('node 1 2\\\n3').statements[0];
        assert.strictEqual(statement.text, 'node 1 23');
        const token = statement.tokens[2];
        assert.strictEqual(token.value, '23');
        assert.strictEqual(token.line, 0);
        assert.strictEqual(token.endLine, 1);
        assert.strictEqual(tokenAt(statement, 0, 7), token);
        assert.strictEqual(tokenAt(statement, 1, 0), token);
        assert.strictEqual(tokenAt(statement, 1, 1), undefined);
    });

    test('locates statements, tokens and token indices', () => {
        const parsed = parseDocument(['node 1 0 0', 'element T2D2 \\', '7 1 2'].join('\n'));
        const element = parsed.statements[1];
        assert.strictEqual(statementAt(parsed, 2), element);
        assert.strictEqual(statementAt(parsed, 3), undefined);
        const tag = element.tokens[2];
        assert.strictEqual(tokenIndex(element, tag), 2);
        assert.strictEqual(
            tokenAt(element, element.tokens[1].line, element.tokens[1].start),
            element.tokens[1]
        );
    });

    test('reports the last line of a dangling continuation', () => {
        const parsed = parseDocument(['node 1 0 0', 'node 2 \\'].join('\n'));
        assert.strictEqual(parsed.danglingContinuation, 1);
        assert.deepStrictEqual(
            parsed.statements.map(statement => statement.text),
            ['node 1 0 0', 'node 2']
        );
    });
});

suite('command database', () => {
    const database = CommandDatabase.load(root);

    test('is generated from the suanPan source', () => {
        assert.match(database.version, /^\d+\.\d+\.\d+$/);
        assert.ok(database.findCommand('element'));
        assert.ok(database.findCommand('analyse'));
    });

    test('contains element and material types', () => {
        assert.ok(database.findType('element', 'T2D2'));
        assert.ok(database.findType('material', 'Elastic1D'));
        assert.strictEqual(database.findType('element', 'not-an-element'), undefined);
    });

    test('resolves type aliases', () => {
        assert.ok(database.findType('step', 'Buckle'));
        const buckling = database.findType('step', 'Buckling');
        assert.ok(buckling?.aliases?.includes('Buckle'));
    });

    test('reads aliases and factories from the unified registry', () => {
        const afc = database.findType('material', 'AFC');
        assert.ok(afc?.aliases?.includes('AFC01'));
        assert.strictEqual(afc?.factory, 'new_afc01');
        assert.strictEqual(database.findType('material', 'CDPM2ISO')?.name, 'CDPM2');

        assert.strictEqual(database.findType('element', 'CPS8')?.name, 'CP8');
        assert.strictEqual(database.findType('element', 'Mass3D')?.name, 'Mass');
        assert.strictEqual(database.findType('section', 'Bar2D')?.name, 'Cell2D');
        assert.strictEqual(database.findType('constraint', 'PenaltyBC')?.name, 'Fix');
        assert.strictEqual(database.findType('constraint', 'MultiplierBC')?.name, 'Fix2');

        const disp = database.findType('load', 'Displacement');
        assert.strictEqual(disp?.name, 'Disp');
        assert.ok(disp?.aliases?.includes('DispLoad'));
    });

    test('every typed category exposes registry types', () => {
        for (const name of [
            'amplitude',
            'constraint',
            'converger',
            'criterion',
            'element',
            'expression',
            'group',
            'integrator',
            'interaction',
            'load',
            'material',
            'modifier',
            'orientation',
            'recorder',
            'section',
            'solver',
            'step',
        ]) {
            const command = database.findCommand(name);
            assert.ok(command, `missing command ${name}`);
            assert.ok((command?.types?.length ?? 0) > 0, `${name} has no types`);
        }
    });

    test('classifies shorthand commands in their real category', () => {
        assert.strictEqual(database.findCommand('nodegroup')?.category, 'group');
        assert.strictEqual(database.findCommand('supportvelocity')?.category, 'load');
        assert.strictEqual(database.findCommand('fix')?.category, 'constraint');
    });

    test('aligns snippets with shorthand and canonical spellings', () => {
        const cload = database.snippetFor('load', ['load', 'cload', '1', '0', '1', '1', '2']);
        assert.strictEqual(cload?.args.find(argument => argument.num === 1)?.tokenIndex, 2);
        const shorthand = database.snippetFor('cload', ['cload', '1', '0', '1', '1', '2']);
        assert.strictEqual(shorthand?.args.find(argument => argument.num === 1)?.tokenIndex, 1);

        const nodegroup = database.snippetFor('nodegroup', ['nodegroup', '3', '1', '2']);
        assert.match(nodegroup?.templates[0] ?? '', /^nodegroup /);
        assert.strictEqual(nodegroup?.args.find(argument => argument.num === 1)?.tokenIndex, 1);

        const embed = database.snippetFor('embed2d', ['embed2d', '1', '2', '3']);
        assert.match(embed?.templates[0] ?? '', /^Embed2D /);
        assert.strictEqual(embed?.args.find(argument => argument.num === 2)?.tokenIndex, 2);
    });

    test('maps ranged and variadic arguments to every covered token', () => {
        const element = ['element', 'CPS8', '1', '1', '2', '3', '4', '5', '6', '7', '8', '2', '1'];
        assert.match(database.argumentFor('element', element, 6)?.description ?? '', /node/);
        assert.match(database.argumentFor('element', element, 11)?.description ?? '', /material/);

        const nodes = ['nodegroup', '3', '1', '2', '4'];
        assert.match(database.argumentFor('nodegroup', nodes, 4)?.description ?? '', /nodes?/);

        const section = ['section', 'NM2D3K', ...Array.from({ length: 15 }, (_, index) => `${index + 1}`)];
        assert.strictEqual(database.argumentFor('section', section, 5)?.num, 4);
        assert.strictEqual(database.argumentFor('section', section, 16)?.num, 15);
    });

    test('exposes set properties', () => {
        assert.ok(database.findType('set', 'num_threads'));
        assert.strictEqual(database.typeTokenIndex('set'), 1);
    });

    test('merges argument documentation from snippets', () => {
        const snippet = database.snippetFor('element', ['element', 'T2D2', '1', '1', '2', '1', '93']);
        assert.ok(snippet);
        const material = snippet?.args.find(argument => /material tag/i.test(argument.description));
        assert.strictEqual(material?.tokenIndex, 5);
    });

    test('recognises named section designations', () => {
        assert.ok(database.designationsFor('NZ2D').length > 0);
        assert.ok(database.designationsFor('EU3D').length > 0);
        assert.ok(database.designationsFor('US2D').length > 0);
    });

    test('reads adjusted coded-section designations from the C++ tables', () => {
        assert.ok(database.designationNamesFor('EU2D').includes('HEA200'));
        assert.ok(database.designationNamesFor('NZ3DA').length > 0);
        // WT22X204 is only listed in the adjusted US T-section registry.
        assert.ok(database.designationNamesFor('US3DA').includes('WT22X204'));
        assert.ok(!database.designationNamesFor('US3D').includes('WT22X204'));

        const snippet = database.snippetFor('section', ['section', 'US2DA', 'WT22X204', '4', '1', '10']);
        assert.ok(snippet);
        assert.match(snippet?.templates[0] ?? '', /^section US2DA WT22X204 /);
    });

    test('rejects unknown coded-section designations in diagnostics data', () => {
        assert.ok(database.designationNamesFor('EU2DA').includes('IPE300'));
        assert.ok(!database.designationNamesFor('EU2DA').includes('not-a-shape'));
        assert.strictEqual(database.designationNamesFor('TrussSection').length, 0);
    });

    test('recognises the modal recorder and its DoF arguments', () => {
        assert.ok(database.findType('recorder', 'Modal'));
        const values = ['recorder', '1', 'hdf5', 'Modal', 'U1', 'U2'];
        const snippet = database.snippetFor('recorder', values);
        assert.strictEqual(snippet?.prefix, 'modal');
        const argument = database.argumentFor('recorder', values, 4);
        assert.match(argument?.description ?? '', /DoF identifiers/);
    });

    test('recognises the modal force recorder', () => {
        assert.ok(database.findType('recorder', 'ModalForce'));
        const values = ['recorder', '2', 'hdf5', 'ModalForce'];
        const snippet = database.snippetFor('recorder', values);
        assert.strictEqual(snippet?.prefix, 'modalforce');
    });

    test('resolves every command name and alias', () => {
        const names = new Set<string>();
        for (const command of database.listCommands()) {
            names.add(command.name);
            assert.strictEqual(database.findCommand(command.name), command);
            for (const alias of command.aliases) {
                names.add(alias);
                assert.strictEqual(database.findCommand(alias), command, `${alias} -> ${command.name}`);
            }
        }
        assert.deepStrictEqual(
            database.commandNames(),
            [...names].sort((a, b) => a.localeCompare(b))
        );
    });

    test('resolves every type keyword and alias in its command', () => {
        let count = 0;
        for (const command of database.listCommands()) {
            const types = database.typesFor(command.name);
            for (const type of types) {
                count++;
                assert.strictEqual(database.findType(command.name, type.name), type);
                for (const alias of type.aliases ?? []) {
                    assert.strictEqual(database.findType(command.name, alias), type, `${alias} -> ${type.name}`);
                }
            }
        }
        assert.ok(count > 400, `only checked ${count} type spellings`);
    });

    test('reports the type token position for every command', () => {
        for (const command of database.listCommands()) {
            const expected =
                command.name === 'recorder'
                    ? 3
                    : command.name === 'hdf5recorder' || command.name === 'plainrecorder'
                      ? 2
                      : command.types?.length
                        ? 1
                        : undefined;
            assert.strictEqual(database.typeTokenIndex(command.name), expected, command.name);
        }
    });

    test('shares recorder types between every recorder spelling', () => {
        const types = database.typesFor('recorder');
        assert.ok(types.length > 0);
        for (const spelling of ['recorder', 'hdf5recorder', 'plainrecorder']) {
            assert.strictEqual(database.typesFor(spelling), types);
            for (const type of types) {
                assert.strictEqual(database.findType(spelling, type.name), type);
            }
        }
    });

    test('keeps snippet metadata well formed for every entry', () => {
        const entries = new Set<SnippetEntry>();
        for (const name of database.commandNames()) {
            for (const entry of database.snippetsFor(name)) entries.add(entry);
        }
        assert.ok(entries.size > 1000, `only found ${entries.size} snippets`);

        for (const entry of entries) {
            assert.ok(entry.templates.length > 0, `no template for ${entry.prefix}`);
            assert.strictEqual(
                entry.templates[0].trim().split(/\s+/)[0].toLowerCase(),
                entry.verb,
                entry.prefix
            );
            assert.ok(database.findCommand(entry.verb), `unknown snippet verb ${entry.verb}`);

            const numbers = entry.args.map(argument => argument.num);
            assert.strictEqual(new Set(numbers).size, numbers.length, entry.prefix);
            for (let index = 1; index < numbers.length; index++) {
                assert.ok(numbers[index] > numbers[index - 1], `${entry.prefix} arguments are not sorted`);
            }
            for (const argument of entry.args) {
                assert.ok(argument.tokenIndex >= -1, `${entry.prefix} argument ${argument.num}`);
                assert.ok(argument.count >= 1, `${entry.prefix} argument ${argument.num}`);
            }
        }
    });

    test('exposes snippets for every alias of a documented type', () => {
        let checked = 0;
        for (const command of database.listCommands()) {
            for (const type of database.typesFor(command.name)) {
                const canonical = database.snippetFor(command.name, [command.name, type.name]);
                if (!canonical) continue;
                for (const alias of type.aliases ?? []) {
                    const aliased = database.snippetFor(command.name, [command.name, alias]);
                    assert.ok(aliased, `missing snippet for ${command.name} ${alias}`);
                    checked++;
                    assert.strictEqual(
                        aliased.args.length,
                        canonical.args.length,
                        `${command.name} ${alias}`
                    );
                    for (const argument of canonical.args) {
                        const other: (typeof canonical.args)[number] | undefined = aliased.args.find(
                            item => item.num === argument.num
                        );
                        assert.ok(other, `${command.name} ${alias} argument ${argument.num}`);
                        assert.strictEqual(other.optional, argument.optional);
                        assert.strictEqual(other.kind, argument.kind);
                        assert.strictEqual(other.description, argument.description);
                    }
                }
            }
        }
        assert.ok(checked > 20, `only checked ${checked} aliases`);
    });
});

suite('document model', () => {
    const database = CommandDatabase.load(root);
    const source = [
        'material Elastic1D 5 200 0.3',
        'section Box2D 6 5',
        'node 1 0 0',
        'node 2 1 0',
        'element T2D2 7 1 2 5 0.1',
    ].join('\n');

    test('collects tags per category', () => {
        const model = buildModel(parseDocument(source), database);
        assert.ok(model.symbols.get('material')?.has(5));
        assert.ok(model.symbols.get('section')?.has(6));
        assert.strictEqual(model.symbols.get('node')?.size, 2);
        assert.ok(model.symbols.get('element')?.has(7));
    });

    test('handles section designations before the tag', () => {
        const model = buildModel(parseDocument('section NZ2D 1000WB215 6 5'), database);
        assert.ok(model.symbols.get('section')?.has(6));
    });

    test('collects tags from shorthand commands', () => {
        const source = [
            'fix 1 E 1 2',
            'displacement 2 0 1 1 1',
            'nodegroup 3 1 2',
            'generate nodegroup 4 1 5',
            'supportvelocity 5 0 1 1 1',
            'group generate nodegroup 6 1 5',
        ].join('\n');
        const model = buildModel(parseDocument(source), database);
        assert.ok(model.symbols.get('constraint')?.has(1));
        assert.ok(model.symbols.get('load')?.has(2));
        assert.ok(model.symbols.get('group')?.has(3));
        assert.ok(model.symbols.get('group')?.has(4));
        assert.ok(model.symbols.get('load')?.has(5));
        assert.ok(model.symbols.get('group')?.has(6));
        assert.strictEqual(model.symbols.get('constraint')?.get(1)?.typeName, 'Fix');
        assert.strictEqual(model.symbols.get('group')?.get(4)?.typeName, 'nodegroup');
        assert.strictEqual(model.symbols.get('group')?.get(6)?.typeName, 'generate');
    });

    test('resolves references from shorthand load commands', () => {
        const parsed = parseDocument('node 1 0 0\ncload 1 0 1 2 1');
        const cload = parsed.statements.find(statement => statement.verb === 'cload');
        assert.ok(cload);
        const reference = referenceAt(cload, 5, database);
        assert.deepStrictEqual([reference?.category, reference?.tag], ['node', 1]);
    });

    test('resolves group references from a groupgroup command', () => {
        const statement = parseDocument('groupgroup 4 1 2 3').statements[0];
        const reference = referenceAt(statement, 3, database);
        assert.deepStrictEqual([reference?.category, reference?.tag], ['group', 2]);
    });

    test('resolves a material reference from element arguments', () => {
        const parsed = parseDocument(source);
        const element = parsed.statements.find(statement => statement.verb === 'element');
        assert.ok(element);
        const reference = referenceAt(element, 5, database);
        assert.deepStrictEqual([reference?.category, reference?.tag], ['material', 5]);
    });

    test('indexes the tag of every object-defining command', () => {
        let checked = 0;
        for (const command of database.listCommands()) {
            const text = definitionFor(command);
            if (!text) continue;
            const category = command.category;
            assert.ok(category, text);
            const parsed = parseDocument(text);
            const statement = parsed.statements[0];
            const tagIndex = tagTokenIndex(statement, database);
            assert.notStrictEqual(tagIndex, undefined, text);

            const model = buildModel(parsed, database);
            const symbol = findSymbol(model, category, 1);
            assert.ok(symbol, `no ${category} symbol for ${text}`);
            assert.strictEqual(symbol.category, category, text);
            assert.strictEqual(symbol.tag, 1, text);
            assert.strictEqual(symbol.statement.verb, statement.verb, text);
            if (TYPED_CATEGORIES.has(category) || category === 'recorder') {
                assert.ok(symbol.typeName, `no type name for ${text}`);
            }
            checked++;
        }
        assert.ok(checked > 60, `only checked ${checked} commands`);
    });

    test('leaves tag-less commands out of the symbol index', () => {
        assert.strictEqual(
            tagTokenIndex(parseDocument('initial material 1').statements[0], database),
            undefined
        );
        assert.strictEqual(
            tagTokenIndex(parseDocument('set num_threads 4').statements[0], database),
            undefined
        );
        assert.strictEqual(
            tagTokenIndex(parseDocument('not-a-command 1').statements[0], database),
            undefined
        );
    });

    test('records definition order and keeps the first duplicate tag', () => {
        const model = buildModel(
            parseDocument(['node 1 0 0', 'node 2 1 0', 'node 1 5 5'].join('\n')),
            database
        );
        assert.strictEqual(model.definitions.length, 3);
        assert.deepStrictEqual(
            model.definitions.map(symbol => symbol.tag),
            [1, 2, 1]
        );
        assert.strictEqual(model.symbols.get('node')?.size, 2);
        assert.strictEqual(findSymbol(model, 'node', 1)?.statement.line, 0);
        assert.deepStrictEqual(
            symbolsOf(model, 'node').map(symbol => symbol.tag),
            [1, 2]
        );
    });

    test('indexes variables case-insensitively and collects domains', () => {
        const model = buildModel(
            parseDocument(['VAR X 1', 'variable y 2', 'domain 1 0 0 1 1', 'node 1 0 0'].join('\n')),
            database
        );
        assert.deepStrictEqual([...model.variables.keys()], ['x', 'y']);
        assert.strictEqual(model.variables.get('x')?.name, 'X');
        assert.strictEqual(model.variables.get('y')?.name, 'y');
        assert.strictEqual(model.domains.length, 1);
        assert.ok(findSymbol(model, 'domain', 1));
    });

    test('maps the type name of canonical, aliased and shorthand commands', () => {
        const cases: Array<[string, string]> = [
            ['constraint Fix 1 E 1', 'Fix'],
            // canonical spellings keep the token as written ...
            ['constraint PenaltyBC 1 E 1', 'PenaltyBC'],
            // ... shorthand commands resolve their own keyword to the class name
            ['fix 1 E 1', 'Fix'],
            ['load Cload 1 0 1 1 2', 'Cload'],
            ['cload 1 0 1 1 2', 'Cload'],
            ['element CP8 1 1 2 3 4 5 6 7 8 1', 'CP8'],
            ['element CPS8 1 1 2 3 4 5 6 7 8 1', 'CPS8'],
            ['group nodegroup 3 1 2', 'nodegroup'],
            ['nodegroup 3 1 2', 'nodegroup'],
            ['group generate nodegroup 4 1 5', 'generate'],
            ['generate nodegroup 4 1 5', 'nodegroup'],
        ];
        for (const [text, expected] of cases) {
            const model = buildModel(parseDocument(text), database);
            assert.strictEqual(model.definitions[0]?.typeName, expected, text);
        }
    });

    test('resolves object management references for every category', () => {
        for (const command of OBJECT_COMMANDS) {
            for (const category of OBJECT_TYPES) {
                const statement = parseDocument(`${command} ${category} 7`).statements[0];
                const reference = referenceAt(statement, 2, database);
                assert.deepStrictEqual(
                    [reference?.category, reference?.tag],
                    [category, 7],
                    `${command} ${category}`
                );
                assert.strictEqual(referenceAt(statement, 1, database), undefined);
            }
        }
    });

    test('does not mistake unrelated numbers for references', () => {
        const cases = [
            ['peek node x', 2],
            ['set num_threads 8', 2],
            ['var x 1', 2],
            ['node 1 0 0', 3],
        ] as const;
        for (const [text, index] of cases) {
            assert.strictEqual(referenceAt(parseDocument(text).statements[0], index, database), undefined, text);
        }
    });

    test('resolves amplitude, section and element references', () => {
        const cases: Array<[string, number, string, number]> = [
            ['load Cload 1 5 100 2 3', 3, 'amplitude', 5],
            ['element T2D2S 1 1 2 5', 5, 'section', 5],
            ['constraint Embed2D 1 4 9', 3, 'element', 4],
        ];
        for (const [text, index, category, tag] of cases) {
            const reference = referenceAt(parseDocument(text).statements[0], index, database);
            assert.deepStrictEqual([reference?.category, reference?.tag], [category, tag], text);
        }
    });
});
