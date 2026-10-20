import * as vscode from 'vscode';

import { CommandDatabase } from './database';
import { Model, buildModel } from './model';
import { parseDocument } from './parser';

/** Caches the parsed model of every open document, keyed by document version. */
export class DocumentCache {
    private readonly entries = new Map<string, { version: number; model: Model }>();

    constructor(private readonly database: CommandDatabase) {}

    get(document: vscode.TextDocument): Model {
        const key = document.uri.toString();
        const cached = this.entries.get(key);
        if (cached && cached.version === document.version) return cached.model;

        const model = buildModel(parseDocument(document.getText()), this.database);
        this.entries.set(key, { version: document.version, model });
        return model;
    }

    forget(document: vscode.TextDocument): void {
        this.entries.delete(document.uri.toString());
    }
}

export interface Runtime {
    database: CommandDatabase;
    cache: DocumentCache;
}
