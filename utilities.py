import featuretools.variable_types as vtypes
import pandas as pd
import featuretools as ft
def learnlab_to_entityset(data):
    # Make an EntitySet called Dataset with the following structure
    #
    # schools       students     problems
    #        \        |         /
    #   classes   sessions   problem steps
    #          \     |       /
    #           transactions  -- attempts
    #
    data.index = data['Transaction Id']
    data = data.drop(['Row'], axis=1)
    #data = data[data['Duration (sec)'] != '.']

    kc_and_cf_cols = [x for x in data.columns if (x.startswith('KC ') or x.startswith('CF '))]
    kc_and_cf_cols.append('Problem Name')
    data['Outcome'] = data['Outcome'].map({'INCORRECT': 0, 'CORRECT': 1})
    data['End Time'] = pd.to_datetime(data['Time']) + pd.to_timedelta(pd.to_numeric(data['Duration (sec)']), 's')


    es = ft.EntitySet('Dataset')
    es.entity_from_dataframe(entity_id='transactions', 
                             index='Transaction Id', 
                             dataframe=data,
                             variable_types={'Outcome': vtypes.Boolean},
                             time_index='Time',
                             secondary_time_index={'End Time': ['Outcome', 'Is Last Attempt', 'Duration (sec)']})
    
    # Two entities associated to problems
    es.normalize_entity(base_entity_id='transactions',
                        new_entity_id='problem_steps',
                        index='Step Name',
                        additional_variables=kc_and_cf_cols,
                        make_time_index=False)

    es.normalize_entity(base_entity_id='problem_steps',
                        new_entity_id='problems',
                        index='Problem Name',
                        make_time_index=False)
    
    
    # Two entities associated to students
    es.normalize_entity(base_entity_id='transactions',
                        new_entity_id='sessions',
                        index='Session Id',
                        additional_variables=['Anon Student Id'],
                        make_time_index=True)

    es.normalize_entity(base_entity_id='sessions',
                        new_entity_id='students',
                        index='Anon Student Id',
                        make_time_index=True)
    
    # Two entities associated to a school
    es.normalize_entity(base_entity_id='transactions',
                        new_entity_id='classes',
                        index='Class',
                        additional_variables=['School'],
                        make_time_index=False)
    
    es.normalize_entity(base_entity_id='classes',
                        new_entity_id='schools',
                        index='School',
                        make_time_index=False)

    # An entity associated to attempts
    es.normalize_entity(base_entity_id='transactions',
                        new_entity_id='attempts',
                        index='Attempt At Step',
                        additional_variables=[],
                        make_time_index=False)
    return es