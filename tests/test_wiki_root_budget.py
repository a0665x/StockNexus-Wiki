"""BDD: short headlines cannot bypass the model's per-turn output budget."""
import unittest
from news_atlas.wiki.forest import groups
from news_atlas.wiki.store import capture
from test_server import row

class RootBudgetTests(unittest.TestCase):
    def tree(self,count):
        rows=[capture(row(title='Tesla earnings '+str(i),suffix=str(i))) for i in range(count)]
        refs=[{'provider':a['provider'],'id':a['id']} for a in rows]
        return rows,{'trees':[{'root_id':'root','articles':refs,'targets':refs}]}

    def test_twelve_members_stay_together_thirteen_split_without_losing_evidence(self):
        for size,parts in [(1,1),(12,1),(13,2),(44,4)]:
            with self.subTest(size=size):
                rows,forest=self.tree(size);work=list(groups(rows,rows,forest))
                self.assertEqual(len(work),parts)
                self.assertTrue(all(len(chunk)<=12 for chunk,_,_ in work))
                self.assertEqual({a['revision_id'] for chunk,_,_ in work for a in chunk},{a['revision_id'] for a in rows})
                self.assertTrue(all(chunk[0]['revision_id']==rows[0]['revision_id'] for chunk,_,_ in work))
                self.assertTrue(all(not covered for _,_,covered in work[:-1]))
                self.assertEqual(work[-1][2],rows)
                self.assertTrue(all(meta['parts']==parts and meta['context_articles']==size for _,meta,_ in work))

    def test_reused_context_stays_but_never_becomes_new_coverage(self):
        rows,forest=self.tree(44);pending=rows[::2]
        work=list(groups(pending,rows,forest))
        self.assertTrue(all(len(chunk)<=12 for chunk,_,_ in work))
        self.assertEqual({a['revision_id'] for chunk,_,_ in work for a in chunk},{a['revision_id'] for a in rows})
        self.assertEqual([a['revision_id'] for _,_,covered in work for a in covered],[a['revision_id'] for a in pending])
