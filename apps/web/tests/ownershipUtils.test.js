import test from 'node:test';
import assert from 'node:assert/strict';
import {ownershipLabel,validateOwnerSelection} from '../src/ownershipUtils.js';
const farmers=[{id:'f1',email:'farmer@example.com'}];
test('unassigned and active farmers are valid',()=>{assert.equal(validateOwnerSelection('',farmers),'');assert.equal(validateOwnerSelection('f1',farmers),'')});
test('unknown farmer is rejected',()=>assert.match(validateOwnerSelection('missing',farmers),/active Farmer/));
test('ownership labels show email or unassigned',()=>{assert.equal(ownershipLabel('',farmers),'Unassigned');assert.equal(ownershipLabel('f1',farmers),'farmer@example.com')});
