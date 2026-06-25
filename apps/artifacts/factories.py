import factory

from apps.projects.factories import ProjectFactory

from .models import Artifact, ArtifactType


class ArtifactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Artifact

    project = factory.SubFactory(ProjectFactory)
    type = ArtifactType.PRD
    title = factory.Sequence(lambda n: f"Artifact {n}")
    body = "## Goals\n- ship it"
    data = factory.LazyFunction(dict)
