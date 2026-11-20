const assert=require('node:assert/strict');
const {build}=require('./floating_fixture.cjs');
const {ui,$,drag}=build();
ui.initSourcePanel($);ui.initTimePanel($);
function separate(){
  const a=$('sourcePanel').getBoundingClientRect(),b=$('timeFocusBar').getBoundingClientRect();
  assert(a.right+8<=b.left||b.right+8<=a.left||a.bottom+8<=b.top||b.bottom+8<=a.top);
}
drag('sourcePanel',-210,-100);
assert.equal($('sourcePanel').getBoundingClientRect().left,46,'Panel whitespace drags across the sidebar');
const before=$('sourcePanel').getBoundingClientRect();
drag('sourcePanel',90,50,{closest:()=>({})});
assert.deepEqual($('sourcePanel').getBoundingClientRect(),before,'Controls retain their own gestures');
drag('sourcePanel',210,430);separate();
$('sourcePanelToggle').onclick();$('timePanelToggle').onclick();separate();
drag('sourcePanel',40,20);separate();
$('sourcePanelDrag').onclick();separate();$('timePanelDrag').onclick();separate();
$('sourcePanelReset').onclick();$('timePanelReset').onclick();separate();
console.log('PASS whole-workbench move, control exclusion, tool collisions, minimize, reopen and reset');
