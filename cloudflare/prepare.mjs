// Build the public frontend and copy only portable Python modules into Workers.
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.dirname(fileURLToPath(import.meta.url));
const backend = path.dirname(root);
const sibling = path.resolve(backend, '../calculator_frontend');
const frontend = existsSync(path.join(sibling, 'package.json')) ? sibling : path.join(root, 'frontend-source');
if (!existsSync(path.join(frontend, 'package.json'))) {
  execFileSync('git', ['clone', '--depth', '1', 'https://github.com/HX-Jan/calculator-frontend.git', frontend], { stdio: 'inherit' });
}
execFileSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['ci'], {cwd: frontend, stdio: 'inherit', shell: process.platform === 'win32'});
execFileSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], {
  cwd: frontend, stdio: 'inherit', shell: process.platform === 'win32', env: {...process.env, VITE_API_BASE_URL: ''},
});
cpSync(path.join(frontend, 'dist'), path.join(root, 'public'), {recursive: true});
mkdirSync(path.join(root, 'src/app'), {recursive: true});
for (const module of ['__init__.py', 'errors.py', 'parser.py', 'scientific.py', 'formula_rules.py', 'cloudflare.py']) {
  cpSync(path.join(backend, 'app', module), path.join(root, 'src/app', module));
}
