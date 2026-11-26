const test=require('node:test'), assert=require('node:assert/strict');
const timeline=require('../dist/timeline.js'), graph=require('../dist/graph-view.js');
test('Given an old article outside 800, when its time cell is selected, then nearby articles can enter the relation calculation',()=>{
 const articles=Array.from({length:1000},(_,i)=>({id:String(i),published_at:new Date(Date.UTC(2022,0,1+i)).toISOString(),primary_channel:'news',source:{provider:'massive'}}));
 const view={articles,relations:[{id:'known',source:'1',target:'2'}]};
 assert.equal(graph.renderSlice(view).relations.length,0);
 const scoped=graph.renderSlice(view,800,timeline.relationPriority(articles,'1'));
 assert.equal(scoped.articles.length,800);assert.equal(scoped.articles[0].id,'1');
 assert.equal(scoped.relations[0].id,'known');
 const model=timeline.density(view,[{id:'news',name:'news'}]);
 assert.equal(model.buckets.length,1000);assert.equal(model.edges.length,1);
 const sameDay={...articles[2],published_at:articles[1].published_at};
 assert.equal(timeline.density({articles:[articles[1],sameDay],relations:view.relations},[{id:'news'}]).edges.length,0);
});
