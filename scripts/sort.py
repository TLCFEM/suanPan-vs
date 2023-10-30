import json

def sort_json(a):
    if isinstance(a, dict):
        return {k: sort_json(v) for k, v in sorted(a.items())}
    
    if isinstance(a, list):
        head = a[0]
        if isinstance(head, dict):
            if 'include' in head:
                return sorted(a, key=lambda x: x['include'])
            if 'matches' in head:
                return sorted(a, key=lambda x: x['matches'])
        
    return a

if __name__ == '__main__':
    with open('syntaxes/.tmLanguage.json', 'r') as f:
        data = json.load(f)

    with open('syntaxes/.tmLanguage.json', 'w') as f:
        f.write(json.dumps(sort_json(data), indent=2))