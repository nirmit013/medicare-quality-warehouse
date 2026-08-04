{#
    CCNs are six-character identifiers with meaningful leading zeros.
    Any step that treats them as numbers strips those zeros, which
    silently breaks joins. Always normalize before comparing.
#}

{% macro clean_ccn(column_name) %}
    lpad(trim({{ column_name }}), 6, '0')
{% endmacro %}
