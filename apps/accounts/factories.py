import factory
from django.contrib.auth import get_user_model

from .models import Membership, Organization, Role, Team

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "pass1234")
        if create:
            obj.save()


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Team {n}")
    slug = factory.Sequence(lambda n: f"team-{n}")


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = Role.MEMBER
