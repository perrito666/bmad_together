import factory

from apps.projects.factories import ProjectFactory

from .models import Epic, Story


class EpicFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Epic

    project = factory.SubFactory(ProjectFactory)
    number = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"Epic {n}")
    goal = "deliver value"


class StoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Story

    epic = factory.SubFactory(EpicFactory)
    number = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"Story {n}")
