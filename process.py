# OpenAlex Metadata Coverage Report
#
# Copyright 2020-21 ######
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Authors: Cameron Neylon, Bianca Kramer
import json
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Optional, Callable, Union

from observatory.reports import report_utils
from precipy.analytics_function import AnalyticsFunction
from report_data_processing.sql import (
    doi_table_categories_query, openalex_table_categories_query
)
from report_graphs import (
    Alluvial, OverallCoverage, BarLine, ValueAddBar, ValueAddByCrossrefType, ValueAddByCrossrefTypeHorizontal,
    PlotlyTable
)

PROJECT_ID = 'utrecht-university'
OPENALEX_DATA_FILENAME = 'openalex_table_data_store.hd5'
CR_DATA_FILENAME = 'doi_table_data_store.hd5'

CURRENT = [2019, 2020, 2021]
LAST_DECADE = range(2010, 2021)


def get_doi_table_data(af: AnalyticsFunction):
    doi_categories = pd.read_gbq(query=doi_table_categories_query,
                                 project_id=PROJECT_ID)

    with pd.HDFStore(CR_DATA_FILENAME) as store:
        store['doi_categories'] = doi_categories

    af.add_existing_file(CR_DATA_FILENAME)


def get_openalex_table_data(af: AnalyticsFunction):
    openalex_categories = pd.read_gbq(query=openalex_table_categories_query,
                                 project_id=PROJECT_ID)

    with pd.HDFStore(OPENALEX_DATA_FILENAME) as store:
        store['openalex_categories'] = openalex_categories

    af.add_existing_file(OPENALEX_DATA_FILENAME)


def load_cache_data(af: AnalyticsFunction,
                    function_name: Union[str, Callable],
                    element: str,
                    filename: Optional[str] = None):
    """Convenience function for loading preprepared DataFrames from the cache

    :param filename:
    :param function_name:
    :param element: Component of the filecache to load
    :param af

    Downloaded query data is collected as DataFrames and stored in and HDFS store as DataFrames. This
    is a convenient function for reloading data from that frame.
    """

    if callable(function_name):
        afunction_name = function_name.__name__
    else:
        afunction_name = function_name

    store_filepath = af.path_to_cached_file(
        filename, afunction_name)

    with pd.HDFStore(store_filepath) as store:
        if f"/{element}" not in store.keys():
            return None
        df = store[element]

    return df


def openalex_coverage_table(af: AnalyticsFunction):
    openalex_data = load_cache_data(af,
                               function_name=get_openalex_table_data,
                               element='openalex_categories',
                               filename=OPENALEX_DATA_FILENAME)

    table_data = openalex_data.groupby('openalex_type').agg(
        openalex_doctype=pd.NamedAgg(column='openalex_type', aggfunc='first'),
        num_openalexids=pd.NamedAgg(column='num_objects', aggfunc='sum'),
        num_dois=pd.NamedAgg(column='num_dois', aggfunc='sum')
    )

    table_data['pc_dois'] = np.round((table_data.num_openalexids / table_data.num_dois * 100), 1)

    openalex_coverage = report_utils.generate_table_data(
        f"Coverage of DOIs in OpenAlex - All Time",
        table_data,
        identifier=None,
        columns=table_data.columns,
        short_column_names=['OpenAlex Doctype', 'Object Count', 'DOIs', 'OpenAlex Records with DOIs (%)'],
        sort_column='Object Count')
    for f in af.generate_file('openalex_coverage_table.json'):
        json.dump(openalex_coverage_table, f)

    table_data.to_csv('openalex_coverage.csv')
    af.add_existing_file('openalex_coverage.csv')


def value_add_tables_graphs(af: AnalyticsFunction):
    cr_data = load_cache_data(af,
                              function_name=get_doi_table_data,
                              element='doi_categories',
                              filename=CR_DATA_FILENAME)

    sum_all = cr_data.sum(axis=0)
    sum_2020 = cr_data[cr_data.published_year == 2020].sum(axis=0)
    sum_current = cr_data[cr_data.published_year.isin(CURRENT)].sum(axis=0)
    # sum_lastdecade = cr_data[cr_data.published_year.isin(LAST_DECADE)].sum(axis=0)

    cols = ['dois_with_cr_affiliation_strings',
            'dois_with_cr_orcid',
            'dois_with_cr_abstract',
            'dois_with_cr_subjects',
            'dois_with_cr_citations',
            'dois_with_cr_references',
            'dois_with_cr_open_references',
            'dois_openalex_aff_string_but_not_cr',
            'dois_with_openalex_author_id_but_not_cr_orcid',
            'dois_with_openalex_not_cr_abstract',
            'dois_with_openalex_field0',
            'dois_with_openalex_field_not_cr_subject',
            'dois_with_openalex_not_cr_citations',
            'dois_more_openalex_citations',
            'dois_with_openalex_not_cr_references',
            'dois_more_openalex_references',
            'dois_with_openalex_not_cr_open_references'
            ]

    summary_table = collate_value_add_values(sum_all, cols)
    summary_table = summary_table.append(collate_value_add_values(sum_current, cols))
    summary_table = summary_table.append(collate_value_add_values(sum_2020, cols))

    summary_table['Time Period'] = ['All Time',
                                    'Crossref Current 2019-21',
                                    '2020 Only']

    for time_period in ['All Time',
                        'Crossref Current 2019-21',
                        '2020 Only']:
        chart = ValueAddBar(df=summary_table[summary_table['Time Period'] == time_period],
                            categories=['Crossref', 'OpenAlex added value'],
                            xs=['Affiliations', 'Abstracts', 'Citations to', 'References from'])
        fig = chart.plotly()
        filename = f'value_add_{time_period.lower().replace(" ", "_")}.'
        fig.write_image(filename + 'png')
        af.add_existing_file(filename + 'png')
        write_plotly_div(af, fig, filename + 'html')

        chart = ValueAddBar(df=summary_table[summary_table['Time Period'] == time_period],
                            categories=['Crossref', 'OpenAlex added value'],
                            xs=['Subjects'],
                            stackedbar=False)
        fig = chart.plotly()
        filename = f'value_add_subject_{time_period.lower().replace(" ", "_")}.'
        fig.write_image(filename + 'png')
        af.add_existing_file(filename + 'png')
        write_plotly_div(af, fig, filename + 'html')

    short_column_names = ['Total DOIs',
                          'CR Affiliation (%)',
                          'CR ORCIDS (%)',
                          'CR Abstract (%)',
                          'CR Subject (%)',
                          'CR Citations to (%)',
                          'CR References from (%)',
                          'CR Open References (%)',
                          'OpenAlex Added Affiliation String (%)',
                          'OpenAlex Added Author ID (%)',
                          'OpenAlex Added Abstract (%)',
                          'OpenAlex With Level 0 Field (%)',
                          'OpenAlex Added Subject (%)',
                          'OpenAlex Added Citations (%)',
                          'OpenAlex Higher Citation Count (%)',
                          'OpenAlex Added References (%)',
                          'OpenAlex Higher Reference Count (%)',
                          'OpenAlex Added to Open References (%)']

    summary_value_add_table = report_utils.generate_table_data('Metadata Coverage and OpenAlex Value Add for Crossref DOIs',
                                                               summary_table,
                                                               columns=['Time Period', 'num_dois'] + [f'pc_{col}' for
                                                                                                      col in cols],
                                                               short_column_names=['Time Period'] + short_column_names,
                                                               identifier=None,
                                                               sort_column=None)

    for f in af.generate_file('summary_doi_metadata_coverage.json'):
        json.dump(summary_value_add_table, f)

    table_plotly = PlotlyTable(table_dict=summary_value_add_table)
    fig = table_plotly.plotly()
    write_plotly_div(af, fig, 'summary_value_add_table.html')

    sum_by_type = cr_data.groupby('cr_type').sum().reset_index()
    summary_table = collate_value_add_values(sum_by_type, cols)

    for metadata_element in ['Abstracts',
                             'Affiliations',
                             'Citations to',
                             'References from']:
        chart = ValueAddByCrossrefType(df=sum_by_type,
                                       metadata_element=metadata_element)
        fig = chart.plotly()
        filename = f'{metadata_element.replace(" ", "_").lower()}_by_cr_type.'
        fig.write_image(filename + 'png')
        af.add_existing_file(filename + 'png')
        write_plotly_div(af, fig, filename + 'html')

    chart = ValueAddByCrossrefType(df=sum_by_type,
                                   metadata_element='Subjects',
                                   stackedbar=False)
    fig = chart.plotly()
    filename = 'subjects_by_cr_type.'
    fig.write_image(filename + 'png')
    af.add_existing_file(filename + 'png')
    write_plotly_div(af, fig, filename + 'html')

    summary_value_add_table = report_utils.generate_table_data(
        'Metadata Coverage and OpenAlex Value Add by Crossref Type - All Time',
        summary_table,
        columns=['cr_type', 'num_dois'] + [f'pc_{col}' for col in cols],
        short_column_names=['Crossref Type'] + short_column_names,
        identifier=None,
        sort_column='Total DOIs',
        sort_ascending=False)

    for f in af.generate_file('summary_doi_metadata_coverage_by_type_alltime.json'):
        json.dump(summary_value_add_table, f)

    sum_2020_by_type = cr_data[cr_data.published_year == 2020].groupby('cr_type').sum().reset_index()
    summary_table = collate_value_add_values(sum_2020_by_type, cols)

    summary_value_add_table = report_utils.generate_table_data(
        'Metadata Coverage and OpenAlex Value Add by Crossref Type - 2020 Publications',
        summary_table,
        columns=['cr_type', 'num_dois'] + [f'pc_{col}' for col in cols],
        short_column_names=['Crossref Type'] + short_column_names,
        identifier=None,
        sort_column='Total DOIs',
        sort_ascending=False)

    for f in af.generate_file('summary_doi_metadata_coverage_by_type_2020.json'):
        json.dump(summary_value_add_table, f)

    sum_current_by_type = cr_data[cr_data.published_year.isin(CURRENT)].groupby('cr_type').sum().reset_index()
    summary_table = collate_value_add_values(sum_current_by_type, cols)

    summary_value_add_table = report_utils.generate_table_data(
        'Metadata Coverage and OpenAlex Value Add by Crossref Type - Current Period',
        summary_table,
        columns=['cr_type', 'num_dois'] + [f'pc_{col}' for col in cols],
        short_column_names=['Crossref Type'] + short_column_names,
        identifier=None,
        sort_column='Total DOIs',
        sort_ascending=False)

    for f in af.generate_file('summary_doi_metadata_coverage_by_type_current.json'):
        json.dump(summary_value_add_table, f)


def collate_value_add_values(df: pd.DataFrame,
                             cols: list):
    """
    Convenience function for cleaning up the value add tables
    :param df: summed data frame from the doi_table_categories_query
    :param cols: type: list set of columns to calculate percentages for
    :return df: type: pd.DataFrame modified dataframe with percentages calculated and all columns remaining
    """

    if type(df) == pd.Series:
        df = pd.DataFrame(df).transpose()

    for col in cols:
        df[f'pc_{col}'] = np.round(df[col] / df['num_dois'] * 100, 1)

    return df


def openalex_coverage_by_cr_type(af: AnalyticsFunction):
    cr_data = load_cache_data(af,
                              function_name=get_doi_table_data,
                              element='doi_categories',
                              filename=CR_DATA_FILENAME)

    cr_total = cr_data.groupby('cr_type').agg(
        num_dois=pd.NamedAgg(column='num_dois', aggfunc='sum'),
        in_openalex=pd.NamedAgg(column='dois_with_openalex_id', aggfunc='sum')
    )
    openalex_with_type = cr_data[~cr_data.openalex_type.isna()].groupby('cr_type').agg(
        openalex_with_type=pd.NamedAgg(column='num_dois', aggfunc='sum')
    )
    openalex_type_is_na = cr_data[cr_data.openalex_type.isna()].groupby('cr_type').agg(
        openalex_type_is_na=pd.NamedAgg(column='num_dois', aggfunc='sum')
    )

    figdata = cr_total.join(openalex_with_type).join(openalex_type_is_na)
    figdata['not_in_openalex'] = figdata.num_dois - figdata.in_openalex
    # OpenAlex Type is also na where there it is not in OpenAlex at all
    figdata['openalex_without_type'] = figdata.openalex_type_is_na - figdata.not_in_openalex
    figdata = collate_value_add_values(figdata, ['openalex_with_type',
                                                 'openalex_without_type',
                                                 'not_in_openalex'])
    figdata.reset_index(inplace=True)

    chart = ValueAddByCrossrefTypeHorizontal(df=figdata,
                                             categories=['in OpenAlex with Document Type',
                                                         'in OpenAlex without Document Type',
                                                         'Not in OpenAlex'],
                                             metadata_element='dummy',
                                             ys={'in OpenAlex with Document Type': {'dummy': 'pc_openalex_with_type'},
                                                 'in OpenAlex without Document Type': {'dummy': 'pc_openalex_without_type'},
                                                 'Not in OpenAlex': {'dummy': 'pc_not_in_openalex'}
                                                 }
                                             )

    # Modify the bar colors here
    fig = chart.plotly(palette=['#F6671E', '#FAA77C', '#CCCCCC'])
    fig.write_image('openalex_coverage_by_crossref_type.png')
    af.add_existing_file('openalex_coverage_by_crossref_type.png')
    write_plotly_div(af, fig, 'openalex_coverage_by_crossref_type.html')


def alluvial_graph(af: AnalyticsFunction):
    cr_data = load_cache_data(af,
                              function_name=get_doi_table_data,
                              element='doi_categories',
                              filename=CR_DATA_FILENAME)
    cr_data_with_nulls = cr_data.replace(to_replace={'cr_type': {
        None: 'no assigned Crossref Type'
    },
        'openalex_type': {
            None: 'no assigned OpenAlex Type'
        }
    }
    )

    figdata = cr_data_with_nulls.groupby(['cr_type', 'openalex_type']).agg(
        num_dois=pd.NamedAgg(column='num_dois', aggfunc='sum')
    )

    cr_order = ['journal-article', 'book-chapter', 'proceedings-article', 'dataset',
                'book', 'journal-issue', 'reference-entry', 'posted-content', 'report',
                'monograph', 'component', 'proceedings', 'report-series', 'book-section',
                'book-part', 'standard', 'book-track', 'other', 'no assigned Crossref Type']
    openalex_order = ['Journal', 'BookChapter', 'Conference', 'Repository', 'Book', 'Patent',
                 'Thesis', 'Dataset', 'no assigned OpenAlex Type']

    figdata.reset_index(inplace=True)
    figdata['cr_type'] = pd.Categorical(figdata.cr_type, categories=cr_order)
    figdata['openalex_type'] = pd.Categorical(figdata.openalex_type, categories=openalex_order)
    figdata.sort_values(['cr_type', 'openalex_type'], inplace=True)

    plot = Alluvial(df=figdata,
                    from_col_name='cr_type',
                    to_col_name='openalex_type',
                    flow_values_col='num_dois')

    plot.process_data()
    fig = plot.plotly()
    fig.write_image('alluvial_all_time.png')
    af.add_existing_file('alluvial_all_time.png')
    write_plotly_div(af, fig, 'alluvial_all_time.html')

    figdata = cr_data_with_nulls[cr_data.published_year.isin(CURRENT)].groupby(['cr_type', 'openalex_type']).agg(
        num_dois=pd.NamedAgg(column='num_dois', aggfunc='sum')
    )

    figdata.reset_index(inplace=True)
    figdata['cr_type'] = pd.Categorical(figdata.cr_type, categories=cr_order)
    figdata['openalex_type'] = pd.Categorical(figdata.openalex_type, categories=openalex_order)
    figdata.sort_values(['cr_type', 'openalex_type'], inplace=True)

    plot = Alluvial(df=figdata,
                    from_col_name='cr_type',
                    to_col_name='openalex_type',
                    flow_values_col='num_dois')

    plot.process_data()
    fig = plot.plotly()

    fig.write_image('alluvial_current.png')
    af.add_existing_file('alluvial_current.png')
    write_plotly_div(af, fig, 'alluvial_current.html')


def calculate_overall_coverage(openalex_data: pd.DataFrame,
                               cr_data: pd.DataFrame) -> dict:
    cr_total = cr_data.num_dois.sum()
    cr_in_openalex = cr_data.dois_with_openalex_id.sum()
    openalex_total = openalex_data.num_objects.sum()
    openalex_with_doi = openalex_data.num_dois.sum()
    openalex_dois_not_cr = openalex_with_doi - cr_in_openalex
    total_objects = cr_total + (openalex_total - openalex_with_doi) + openalex_dois_not_cr
    total_dois = cr_total + openalex_dois_not_cr
    objects_wo_dois = total_objects - total_dois

    return dict(
        total_objects=total_objects,
        total_dois=total_dois,
        objects_wo_dois=objects_wo_dois,
        openalex_no_doi=openalex_total - openalex_with_doi,
        openalex_dois_not_cr=openalex_dois_not_cr,
        cr_in_openalex=cr_in_openalex,
        cr_not_in_openalex=cr_total - cr_in_openalex,
        cr_total=cr_total
    )


def overall_comparison(af: AnalyticsFunction):
    cr_data = load_cache_data(af,
                              function_name=get_doi_table_data,
                              element='doi_categories',
                              filename=CR_DATA_FILENAME)

    cr_sum_all = cr_data.sum(axis=0)
    cr_sum_2020 = cr_data[cr_data.published_year == 2020].sum(axis=0)
    cr_sum_current = cr_data[cr_data.published_year.isin(CURRENT)].sum(axis=0)

    openalex_data = load_cache_data(af,
                               function_name=get_openalex_table_data,
                               element='openalex_categories',
                               filename=OPENALEX_DATA_FILENAME)

    openalex_sum_all = openalex_data.sum(axis=0)
    openalex_sum_2020 = openalex_data[openalex_data.Year == 2020].sum(axis=0)
    openalex_sum_current = openalex_data[openalex_data.Year.isin(CURRENT)].sum(axis=0)

    figdata_all = calculate_overall_coverage(openalex_sum_all, cr_sum_all)
    chart = OverallCoverage(figdata_all,
                            line_offset=0.06)
    # line_offset=0.08)
    fig = chart.plotly()
    fig.write_image('overall_coverage.png')
    af.add_existing_file('overall_coverage.png')
    write_plotly_div(af, fig, 'overall_coverage.html')

    figdata_2020 = calculate_overall_coverage(openalex_sum_2020, cr_sum_2020)
    chart = OverallCoverage(figdata_2020,
                            line_offset=0.06)
    # line_offset=0.08)
    fig = chart.plotly()
    fig.write_image('2020_coverage.png')
    af.add_existing_file('2020_coverage.png')

    figdata_current = calculate_overall_coverage(openalex_sum_current, cr_sum_current)
    chart = OverallCoverage(figdata_current,
                            line_offset=0.06)
    # line_offset=0.08)
    fig = chart.plotly()
    fig.write_image('current_coverage.png')
    af.add_existing_file('current_coverage.png')
    write_plotly_div(af, fig, 'current_coverage.html')


def openalex_in_crossref_by_pubdate(af):
    cr_data = load_cache_data(af,
                              function_name=get_doi_table_data,
                              element='doi_categories',
                              filename=CR_DATA_FILENAME)

    openalex_data = load_cache_data(af,
                               function_name=get_openalex_table_data,
                               element='openalex_categories',
                               filename=OPENALEX_DATA_FILENAME)

    year_range = range(1980, 2022)

    figdata = pd.DataFrame(index=year_range,
                           data=[calculate_overall_coverage(
                               openalex_data=openalex_data[openalex_data.Year == year],
                               cr_data=cr_data[cr_data.published_year == year])
                               for year in year_range])

    figdata['pc_openalex_in_cr'] = figdata.cr_in_openalex / figdata.cr_total * 100

    chart = BarLine(xdata=figdata.index,
                    bardata=figdata.cr_total,
                    linedata=figdata.pc_openalex_in_cr)

    fig = chart.plotly()

    fig.write_image('cr_in_openalex_barline.png')
    af.add_existing_file('cr_in_openalex_barline.png')
    write_plotly_div(af, fig, 'cr_in_openalex_barline.html')


def write_plotly_div(af: AnalyticsFunction,
                     figure: go.Figure,
                     filename: Union[str, Path],
                     full_html: Optional[bool] = True,
                     include_plotlyjs: Optional[Union[str, bool]] = True,
                     auto_play: Optional[bool] = False):
    h = figure.to_html(filename,
                       full_html=full_html,
                       include_plotlyjs=include_plotlyjs,
                       auto_play=auto_play)

    for f in af.generate_file(filename):
        f.write(h)
