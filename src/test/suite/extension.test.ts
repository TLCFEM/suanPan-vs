import * as assert from 'assert';
import * as path from 'path';

import { CommandDatabase } from '../../core/database';
import { buildModel, referenceAt } from '../../core/model';
import { parseDocument } from '../../core/parser';

const root = path.resolve(__dirname, '../../..');

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
});
