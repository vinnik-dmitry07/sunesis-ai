// The export must refuse cases that activate Ginzu branches the Python port does not model.
import test from 'node:test';
import assert from 'node:assert/strict';
import {loadPage, originalOverrides} from '../lib/page.mjs';
import {unsupportedFeatures} from '../lib/scope.mjs';

const P = await loadPage();
const ORIGINAL = originalOverrides(P.data);
const e = new P.WorkbookEngine(P.book, ORIGINAL);
const check = changes => { e.reset({...ORIGINAL, ...changes}); return unsupportedFeatures(e); };

test('the original case is inside the supported scope', () => assert.deepEqual(check({}), []));
test('an active NOL is refused', () => assert.match(check({'Input sheet!B61': 'Yes', 'Input sheet!B62': 25}).join(), /net operating loss/));
test('a distress adjustment is refused', () => assert.match(check({'Input sheet!B51': 'Yes', 'Input sheet!B52': 0.1}).join(), /distress/));
test('trapped cash is refused', () => assert.match(check({'Input sheet!B70': 'Yes'}).join(), /trapped cash/));
test('a reinvestment lag other than one year is refused', () => assert.match(check({'Input sheet!B56': 'Yes', 'Input sheet!B57': 2}).join(), /reinvestment lag/));
test('a lag override that keeps one year is accepted', () => assert.deepEqual(check({'Input sheet!B56': 'Yes', 'Input sheet!B57': 1}), []));
