WITH doi_prefixes AS (

SELECT
  member_id as cr_member,
  prefix as cr_prefix,
  reference_visibility as cr_ref_visibility

FROM `utrecht-university.crossref_lookup.crossref_member_prefixes_20210618`
),

doi_table AS (

SELECT *

FROM `utrecht-university.OpenAlex_intermediate.DOI_table_OpenAlex_20211011` as a

LEFT JOIN doi_prefixes as b

ON a.crossref.member = b.cr_member
AND a.crossref.prefix = b.cr_prefix
),


truth_table AS (
    SELECT
        doi,
        crossref.type as cr_type,
        openalex.DocType as openalex_type,
        crossref.published_year,
        CASE
            WHEN openalex.PaperId is not Null THEN TRUE
            ELSE FALSE
        END
        as has_openalex_id,
        CASE
            WHEN (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors, UNNEST(authors.affiliation) AS affiliation WHERE affiliation.name is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_affiliation_string,
        CASE
            WHEN
                (SELECT COUNT(1) from UNNEST(openalex.authors) AS mauthors where mauthors.OriginalAffiliation is not null) > 0  THEN TRUE
            ELSE FALSE
        END
        as has_openalex_aff_string,
        CASE
            WHEN
                (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors, UNNEST(authors.affiliation) AS affiliation WHERE affiliation.name is not null) = 0
                and
                (SELECT COUNT(1) from UNNEST(openalex.authors) AS mauthors where mauthors.OriginalAffiliation is not null) > 0  THEN TRUE
            ELSE FALSE
        END
        as has_openalex_aff_string_not_cr_affiliation,
        CASE
            WHEN (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors WHERE authors.authenticated_orcid is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_authenticated_orcid,
        CASE
            WHEN (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors WHERE authors.ORCID is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_orcid,
        CASE
            WHEN
                ((SELECT COUNT(1) FROM UNNEST(openalex.authors) AS mauthors WHERE mauthors.AuthorId is not null) > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_authorid,
        CASE
            WHEN
                ((SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors WHERE authors.ORCID is not null) = 0) AND
                ((SELECT COUNT(1) FROM UNNEST(openalex.authors) AS mauthors WHERE mauthors.AuthorId is not null) > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_authorid_not_cr_orcid,
        CASE
            WHEN (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors WHERE authors.family is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_author_name,
        CASE
            WHEN
                (SELECT COUNT(1) FROM UNNEST(openalex.authors) AS mauthors WHERE mauthors.OriginalAuthor is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_openalex_author_name,
        CASE
            WHEN
                (SELECT COUNT(1) FROM UNNEST(crossref.author) AS authors WHERE authors.family is not null) = 0
                AND
                (SELECT COUNT(1) FROM UNNEST(openalex.authors) AS mauthors WHERE mauthors.OriginalAuthor is not null) > 0 THEN TRUE
            ELSE FALSE
        END
        as has_openalex_not_cr_author_name,
        CASE
            WHEN (crossref.abstract is not null) THEN TRUE
            ELSE FALSE
        END
        as has_cr_abstract,
        CASE
            WHEN (openalex.abstract is not null) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_abstract,
        CASE
            WHEN
                (crossref.abstract is null) AND
                (openalex.abstract is not null) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_not_cr_abstract,
        CASE
            WHEN crossref.is_referenced_by_count > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_citations,
        CASE
            WHEN (openalex.CitationCount > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_citations,
        CASE
            WHEN (crossref.is_referenced_by_count = 0) and (openalex.CitationCount > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_no_cr_citations,
        CASE
            WHEN (crossref.is_referenced_by_count = openalex.CitationCount) THEN "EQUAL"
            WHEN (crossref.is_referenced_by_count > openalex.CitationCount) THEN "MORE_CR"
            WHEN (crossref.is_referenced_by_count < openalex.CitationCount) THEN "MORE_OPENALEX"
            ELSE "FALSE"
        END
        as openalex_vs_cr_cites,
        CASE
            WHEN crossref.references_count > 0 THEN TRUE
            ELSE FALSE
        END
        as has_cr_references,
        CASE
            WHEN (openalex.ReferenceCount > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_references,
        CASE
            WHEN (crossref.references_count = 0) and (openalex.ReferenceCount > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_no_cr_references,
        CASE
            WHEN (crossref.references_count = openalex.ReferenceCount) THEN "EQUAL"
            WHEN (crossref.references_count > openalex.ReferenceCount) THEN "MORE_CR"
            WHEN (crossref.references_count < openalex.ReferenceCount) THEN "MORE_OPENALEX"
            ELSE "FALSE"
        END
        as openalex_vs_cr_references,
        CASE
            WHEN (crossref.references_count > 0) and (cr_ref_visibility = 'open') THEN TRUE
            ELSE FALSE
        END
        as has_cr_open_references,
    
        CASE
            WHEN (crossref.references_count = 0) and (openalex.ReferenceCount > 0) THEN TRUE
            WHEN (crossref.references_count > 0) and (cr_ref_visibility != 'open') and (openalex.ReferenceCount > 0) THEN TRUE
            ELSE FALSE
        END
        as has_openalex_no_cr_open_references,

        CASE
            WHEN ARRAY_LENGTH(crossref.subject) > 0 THEN crossref.subject[OFFSET(0)]
            ELSE null
        END as
        cr_top_subject,
        CASE
            WHEN ARRAY_LENGTH(crossref.subject) > 0 THEN ARRAY_TO_STRING(crossref.subject, ";")
            ELSE null
        END as
        cr_concat_subjects,

        CASE
            WHEN ARRAY_LENGTH(crossref.subject) > 0 THEN ARRAY_LENGTH(crossref.subject)
            ELSE null
        END as num_cr_subjects,

        CASE
            WHEN (ARRAY_LENGTH(openalex.fields.level_0) > 0) THEN ARRAY_LENGTH(openalex.fields.level_0)
            ELSE null
        END as
        num_openalex_field0,
        CASE
            WHEN (ARRAY_LENGTH(crossref.subject) = 0) AND (ARRAY_LENGTH(openalex.fields.level_0) > 0) THEN TRUE
            ELSE FALSE
        END as
        has_openalex_field0_not_cr_subject,

    FROM doi_table
)

SELECT
    published_year,
    cr_type,
    openalex_type,
    COUNT(doi) as num_dois,
    COUNTIF(has_openalex_id) as dois_with_openalex_id,

    COUNTIF(has_cr_affiliation_string) as dois_with_cr_affiliation_strings,
    COUNTIF(has_openalex_aff_string) as dois_with_openalex_affiliation_strings,
    COUNTIF(has_openalex_aff_string_not_cr_affiliation) as dois_openalex_aff_string_but_not_cr,

    COUNTIF(has_cr_orcid) as dois_with_cr_orcid,
    COUNTIF(has_cr_authenticated_orcid) as doi_with_cr_authenticated_orcid,
    COUNTIF(has_openalex_authorid) as dois_with_openalex_author_id,
    COUNTIF(has_openalex_authorid_not_cr_orcid) as dois_with_openalex_author_id_but_not_cr_orcid,

    COUNTIF(has_cr_author_name) as dois_with_cr_author_name,
    COUNTIF(has_openalex_author_name) as dois_with_openalex_author_name,
    COUNTIF(has_openalex_not_cr_author_name) as dois_with_openalex_not_cr_author_name,

    COUNTIF(has_cr_abstract) as dois_with_cr_abstract,
    COUNTIF(has_openalex_abstract) as dois_with_openalex_abstract,
    COUNTIF(has_openalex_not_cr_abstract) as dois_with_openalex_not_cr_abstract,

    COUNTIF(has_cr_citations) as dois_with_cr_citations,
    COUNTIF(has_openalex_citations) as dois_with_openalex_citations,
    COUNTIF(has_openalex_no_cr_citations) as dois_with_openalex_not_cr_citations,
    COUNTIF(openalex_vs_cr_cites = "EQUAL") as dois_same_openalex_cr_citations,
    COUNTIF(openalex_vs_cr_cites = "MORE_CR") as dois_more_cr_citations,
    COUNTIF(openalex_vs_cr_cites = "MORE_OPENALEX") as dois_more_openalex_citations,

    COUNTIF(has_cr_references) as dois_with_cr_references,
    COUNTIF(has_openalex_references) as dois_with_openalex_references,
    COUNTIF(has_openalex_no_cr_references) as dois_with_openalex_not_cr_references,
    COUNTIF(openalex_vs_cr_references = "EQUAL") as dois_same_openalex_cr_references,
    COUNTIF(openalex_vs_cr_references = "MORE_CR") as dois_more_cr_references,
    COUNTIF(openalex_vs_cr_references = "MORE_OPENALEX") as dois_more_openalex_references,
    
    COUNTIF(has_cr_open_references) as dois_with_cr_open_references,
    COUNTIF(has_openalex_no_cr_open_references) as dois_with_openalex_not_cr_open_references,

    COUNTIF(num_cr_subjects is not null) as dois_with_cr_subjects,
    COUNTIF(num_openalex_field0 is not null) as dois_with_openalex_field0,
    COUNTIF(has_openalex_field0_not_cr_subject) as dois_with_openalex_field_not_cr_subject

FROM truth_table

GROUP BY published_year, cr_type, openalex_type
ORDER BY published_year DESC, cr_type ASC, openalex_type ASC
