from django.core.paginator import Paginator

from rest_framework import serializers


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop("fields", None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class DynamicDepthModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `depth` argument that
    controls the depth for which to expand nested fields.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'depth' arg up to the superclass
        depth = kwargs.pop("depth", None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if depth is not None:
            self.Meta.depth = int(depth)


class UpdateListSerializer(serializers.ListSerializer):
    def update(self, instances, validated_data):
        instance_hash = {index: instance for index, instance in enumerate(instances)}

        result = [
            self.child.update(instance_hash[index], attrs)
            for index, attrs in enumerate(validated_data)
        ]

        return result


def paginate_objects(objects, page_num, per_page):
    paginator = Paginator(objects, per_page)
    page = paginator.page(page_num)
    response = {
        "count": paginator.count,
        "next": page.next_page_number() if page.has_next() else None,
        "previous": page.previous_page_number() if page.has_previous() else None,
        "results": page.object_list,
    }
    return response
