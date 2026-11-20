import test from 'node:test';
import assert from 'node:assert/strict';
import {decisionLabel,validateReview} from '../src/reviewUtils.js';

test('approval permits an empty note',()=>assert.equal(validateReview('approved',''),''));
test('rejection and correction require notes',()=>{assert.match(validateReview('rejected',''),/required/);assert.match(validateReview('correction_requested','  '),/required/)});
test('invalid and oversized reviews are rejected',()=>{assert.match(validateReview('unknown','x'),/valid/);assert.match(validateReview('rejected','x'.repeat(2001)),/2000/)});
test('decision labels are readable',()=>assert.equal(decisionLabel('correction_requested'),'Request Correction'));
