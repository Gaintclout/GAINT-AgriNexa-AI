import test from 'node:test';
import assert from 'node:assert/strict';
import {buildParcelQuery,parseParcelFeatures} from '../src/gisUtils.js';
const bounds={west:78,south:17,east:79,north:18};
test('serializes map bounds and normalized filters',()=>{
 const query=buildParcelQuery(bounds,{village_code:' TG01 ',external_id:' P001 '});
 assert.equal(query.get('village_code'),'TG01');
 assert.equal(query.get('external_id'),'P001');
 assert.equal(query.get('limit'),'500');
 assert.equal(query.get('west'),'78');
});
test('omits blank filters',()=>{
 const query=buildParcelQuery(bounds,{village_code:' '});
 assert.equal(query.has('village_code'),false);
});
test('rejects invalid bounds',()=>{
 assert.throws(()=>buildParcelQuery({...bounds,west:80}));
 assert.throws(()=>buildParcelQuery({...bounds,north:Infinity}));
});
test('rejects overly long filters',()=>{
 assert.throws(()=>buildParcelQuery(bounds,{external_id:'x'.repeat(101)}));
});
test('validates GeoJSON feature collection',()=>{
 const data={type:'FeatureCollection',features:[{type:'Feature',id:'p1',geometry:{type:'MultiPolygon',coordinates:[]},properties:{external_id:'P1'}}]};
 assert.equal(parseParcelFeatures(data),data);
 assert.throws(()=>parseParcelFeatures({type:'FeatureCollection',features:[{}]}));
 assert.throws(()=>parseParcelFeatures({type:'Feature',features:[]}));
});
