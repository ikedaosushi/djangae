import logging
from django.db import models
from djangae.test import TestCase
from djangae.test import process_task_queues
from djangae.contrib.mapreduce.input_readers import DjangoInputReader
import webapp2
from mapreduce.mapreduce_pipeline import MapreducePipeline


class TestNode(models.Model):
    data = models.CharField(max_length=32)
    counter = models.IntegerField()


class DjangoInputReaderTestCase(TestCase):

    def setUp(self):
        for x in range(100):
            self.testnode = TestNode()
            self.testnode.data = 'Lol'
            self.testnode.counter = 1
            self.testnode.save()
        super(DjangoInputReaderTestCase, self).setUp()

    def test_split_input(self):
        from mapreduce.model import MapperSpec
        shards = 12
        mapper_spec = MapperSpec(
            '',
            '',
            {
                'input_reader': {
                    'model': 'mapreduce.TestNode'
                }
            },
            shards,
        )
        readers = DjangoInputReader.split_input(mapper_spec)
        self.assertEqual(len(readers), shards)
        models = []
        for reader in readers:
            for model in reader:
                models.append(model.pk)
        self.assertEqual(len(models), 100)
        self.assertEqual(len(models), len(set(models)))


class MapreduceTestCase(TestCase):

    def setUp(self):
        for x in range(20):
            self.testnode = TestNode()
            self.testnode.data = 'Lol'
            self.testnode.counter = 1
            self.testnode.save()
        super(MapreduceTestCase, self).setUp()

    def test_mapreduce_basic(self):
        """
            Tests basic mapreduce with random input
        """
        pipe = MapreducePipeline(
            "word_count",
            "djangae.contrib.mapreduce.tests.letter_count_map",
            "djangae.contrib.mapreduce.tests.word_count_reduce",
            "mapreduce.input_readers.RandomStringInputReader",
            "mapreduce.output_writers.GoogleCloudStorageOutputWriter",
            mapper_params={'count': 10},
            reducer_params={"mime_type": "text/plain", 'output_writer': {'bucket_name': 'test'}},
            shards=1
        )
        pipe.start()
        process_task_queues()

    def test_mapreduce_django_input(self):
        """
            Test basic django operations inside a map task, this shows that
            our handlers are working
        """
        nodes = TestNode.objects.all()
        for node in nodes:
            self.assertEqual(node.counter, 1)
        pipe = MapreducePipeline(
            "word_count",
            "djangae.contrib.mapreduce.tests.model_counter_increment",
            "djangae.contrib.mapreduce.tests.word_count_reduce",
            "djangae.contrib.mapreduce.input_readers.DjangoInputReader",
            "mapreduce.output_writers.GoogleCloudStorageOutputWriter",
            mapper_params={'count': 10, 'input_reader': {'model': 'mapreduce.TestNode'}},
            reducer_params={"mime_type": "text/plain", 'output_writer': {'bucket_name': 'test'}},
            shards=5
        )
        pipe.start()
        process_task_queues()
        nodes = TestNode.objects.all()
        for node in nodes:
            self.assertEqual(node.counter, 2)


def letter_count_map(data):
    """Word Count map function."""
    letters = [x for x in data]
    for l in letters:
        yield (l, "")

def model_counter_increment(instance):
    """Word Count map function."""
    instance.counter += 1
    instance.save()
    yield (instance.pk, "")

def word_count_reduce(key, values):
    """Word Count reduce function."""
    yield "%s: %d\n" % (key, len(values))
