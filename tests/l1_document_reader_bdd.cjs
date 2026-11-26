// Run the shipped document reader and its event handlers against versioned API responses.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');

test('Given a Wiki quote in an older revision, open the pinned paragraph and highlight its original Unicode span',async()=>{
  const w=new JSDOM(fs.readFileSync('dist/documents.html','utf8'),{
    url:'http://fixture.local/documents?collection=research&source=interviews&id=capacity&revision=1&start=2&end=6',
    runScripts:'outside-only'
  }).window;
  const record={id:'capacity',kind:'section',source:'interviews',title:'供應商訪談',locator:{page:12}};
  const requested=[];
  w.fetch=async url=>{
    const p=new w.URL(url,w.location).searchParams;
    requested.push(p);
    const body=p.has('id')?{record:{...record,text:'🟢：產能提升。'},revision:1}:
      p.has('collection')?{nodes:[{...record,text:'這是已修訂的說法',revision:2}]}:
      {collections:[{id:'research',sources:{interviews:1}}]};
    return {ok:true,json:async()=>body};
  };
  try{
    w.eval(fs.readFileSync('dist/documents.js','utf8'));
    await new Promise(resolve=>setImmediate(resolve));
    const details=w.document.querySelector('#details');
    assert.match(details.textContent,/v1/);
    assert.match(details.textContent,/p. 12/);
    assert.equal(details.querySelector('mark').textContent,'產能提升');
    assert.equal(requested.at(-1).get('revision'),'1');
  }finally{w.close();}
});

test('Given a confirmed stock on the news graph, the import link carries that stock even before the first collection exists',()=>{
  const w=new JSDOM('<a href="/documents#importDocuments">Import</a><div id="documentLauncher"><select id="documentCollection"></select><div id="documentChoices"></div></div>',{url:'http://fixture.local',runScripts:'outside-only'}).window;
  try{
    w.AtlasWikiContext={confirmedSearch:()=>({instrument:'NASDAQ:NVDA'})};
    w.fetch=()=>new Promise(()=>{});
    w.eval(fs.readFileSync('dist/documents.js','utf8'));
    const link=w.document.querySelector('a');
    link.dispatchEvent(new w.Event('focus'));
    assert.equal(link.href,'http://fixture.local/documents?instrument=NASDAQ%3ANVDA#importDocuments');
  }finally{w.close();}
});
