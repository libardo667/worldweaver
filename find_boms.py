import os

def find_boms(start_dir):
    boms = []
    for root, dirs, files in os.walk(start_dir):
        if '.git' in dirs:
            dirs.remove('.git')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        header = f.read(3)
                        if header == b'\xef\xbb\xbf':
                            boms.append(path)
                except Exception as e:
                    print(f"Error reading {path}: {e}")
    return boms

if __name__ == "__main__":
    targets = find_boms('.')
    for t in targets:
        print(t)
