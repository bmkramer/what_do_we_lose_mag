WITH table AS (
SELECT
    *,
    CASE
        WHEN Doi is not null THEN TRUE
        ELSE FALSE
      END
        as has_doi
FROM `academic-observatory.OpenAlex.Papers20211011`
)

SELECT
    Year,
    Doctype,
    has_doi,
    count(PaperId) as count,
    countif(Doi IS NOT NULL) as count_doi
FROM table
GROUP BY Year, Doctype, has_doi
ORDER BY count DESC