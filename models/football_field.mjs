import {readFileSync,writeFileSync} from 'node:fs';
import vm from 'node:vm';
import {root} from './engine.mjs';

const html=readFileSync(`${root}index.html`,'utf8'),nodes=new Map();
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{innerHTML:''});return nodes.get(id);}};
const context=vm.createContext({document,window:{},console,setTimeout,clearTimeout});
const code=html.slice(html.indexOf('const BUNDLED_BOOK='),html.lastIndexOf('\ninit();'));
vm.runInContext(code+`
  book=BUNDLED_BOOK;data=BUNDLED_CASE;initValuationBook();
  baseline=new WorkbookEngine(book);engine=new WorkbookEngine(book);
  renderValuation();`,context,{timeout:10000});
const svg=nodes.get('valuation-content').innerHTML.match(/<svg[\s\S]*?<\/svg>/)?.[0];
if(!svg)throw new Error('The page did not render a football field.');
writeFileSync(`${root}models/out/football_field.svg`,svg.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, sans-serif" '));
