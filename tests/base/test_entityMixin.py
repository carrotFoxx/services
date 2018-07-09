from unittest import TestCase

from microcore.entity.model import EntityMixin


class TestEntityMixin(TestCase):
    def test_map_fields_from_dict(self):
        class SampleInheritor(EntityMixin):
            def __init__(self, **properties):
                super().__init__()
                self.existing_property = None
                self.map_fields_from_dict(properties)

        with self.assertRaises(AttributeError):
            SampleInheritor(non_existing_property=1)

        s = SampleInheritor(existing_property=1)
        self.assertEqual(s.existing_property, 1)
