"""Combination semantics, saved preferences and real context integration (isolated DB)."""
import unittest
import test_companion_experience as fixtures
from _source_path import load

rules_module = load('ai_doll.core.body_combinations')
RULES = [dict(name='拥抱', channels=[0, 1], window_ms=1500)]


class CombinationContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ExperienceTests();self.fixture.setUp()
        self.c=self.fixture.c;self.event=self.fixture.event

    def tearDown(self):
        self.fixture.tearDown()

    def test_cross_cursor_overlap_and_release(self):
        self.c.experience.update_preferences({'body_combinations': RULES})
        self.event(1, age=2, channel=0, touch='a')
        self.event(2, age=1.5, channel=1, touch='b')
        context=self.c.experience.context('combo-chat', after=1)
        self.assertEqual([e['channel'] for e in context['events']], [1])
        self.assertEqual(context['combinations'][0]['name'], '拥抱')
        self.c.db.execute('DELETE FROM events WHERE seq=2');self.c.db.commit()
        self.event(2, phase='end', age=1.8, channel=0, touch='a')
        self.event(3, age=1.5, channel=1, touch='b')
        self.assertEqual(self.c.experience.context('combo-chat')['combinations'], [])

    def test_rule_validation_keeps_previous_preferences(self):
        self.c.experience.update_preferences({'body_combinations': RULES})
        for bad in ([dict(name='拥抱',channels=[0,0])], [dict(name='x',channels=[True,1])], RULES*2):
            with self.assertRaises(ValueError):self.c.experience.update_preferences({'body_combinations':bad})
        self.assertEqual(self.c.experience.preferences()['body_combinations'], RULES)
        self.c.experience.update_preferences({'body_combinations':[]})
        self.assertEqual(self.c.experience.preferences()['body_combinations'], [])

    def test_combo_can_complete_after_single_touch_ack(self):
        self.c.experience.update_preferences({'body_combinations': RULES})
        self.event(1, age=2, channel=0, touch='a')
        first=self.c.experience.context('ack-chat')
        self.c.experience.acknowledge('ack-chat', first['receipt_id'])
        self.event(2, age=1.5, channel=1, touch='b')
        second=self.c.experience.context('ack-chat', after=1)
        self.assertEqual(second['combinations'][0]['name'], '拥抱')


class CombinationSemanticsTests(unittest.TestCase):
    def test_release_source_boot_and_window(self):
        a=dict(id=1,at=100,channel=0,phase='start',touch_id='a',boot='b',quality='ok',source='sensor')
        b=dict(a,id=2,at=100.5,channel=1,touch_id='b')
        match=rules_module.recognize([a,b],RULES)
        self.assertEqual(len(match),1)
        for change in ({'source':'simulation'},{'boot':'new'},{'at':102},{'quality':'fault'},{'delivery_quality':'offline_replay'}):
            self.assertEqual(rules_module.recognize([a,dict(b,**change)],RULES),[])
        self.assertEqual(rules_module.recognize([dict(a,ended_at=100.2),b],RULES),[])
        self.assertEqual(rules_module.recognize([a,dict(a,id=3,phase='end',at=100.2),b],RULES),[])


if __name__=='__main__':unittest.main()
