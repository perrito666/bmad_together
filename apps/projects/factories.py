import factory

from apps.accounts.factories import OrganizationFactory, UserFactory

from .models import Project


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    organization = factory.SubFactory(OrganizationFactory)
    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Project {n}")
    slug = factory.Sequence(lambda n: f"project-{n}")
