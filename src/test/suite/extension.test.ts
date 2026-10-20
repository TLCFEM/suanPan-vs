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

    test('resolves a material reference from element arguments', () => {
        const parsed = parseDocument(source);
        const element = parsed.statements.find(statement => statement.verb === 'element');
        assert.ok(element);
        const reference = referenceAt(element, 5, database);
        assert.deepStrictEqual([reference?.category, reference?.tag], ['material', 5]);
    });
});
