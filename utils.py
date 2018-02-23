import featuretools.variable_types as vtypes
import pandas as pd
import featuretools as ft
from featuretools.primitives import Sum, Mean, Median, Count, Hour
from featuretools.selection import remove_low_information_features
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score


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


def autorun_dfs(es, target_entity='transactions',
                label='Outcome', custom_agg=[]):
    cutoff_times = es[target_entity].df[['Transaction Id', 'End Time', label]]
    fm, features = ft.dfs(entityset=es,
                          target_entity='transactions',
                          agg_primitives=[Sum, Mean] + custom_agg,
                          trans_primitives=[Hour],
                          max_depth=3,
                          approximate='2m',
                          cutoff_time=cutoff_times,
                          verbose=True)
    fm_enc, _ = ft.encode_features(fm, features)
    fm_enc = fm_enc.fillna(0)
    fm_enc = remove_low_information_features(fm_enc)
    labels = fm.pop(label)
    return (fm_enc, labels)


def score_with_tssplit(fm_enc, label, splitter):
    k = 0
    for train_index, test_index in splitter.split(fm_enc):
        clf = RandomForestClassifier()
        X_train, X_test = fm_enc.iloc[train_index], fm_enc.iloc[test_index]
        y_train, y_test = label[train_index], label[test_index]
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        score = round(roc_auc_score(preds, y_test), 2)
        print("AUC score on time split {} is {}".format(k, score))
        feature_imps = [(imp, fm_enc.columns[i]) for i, imp in enumerate(clf.feature_importances_)]
        feature_imps.sort()
        feature_imps.reverse()
        print("Top 5 features: {}".format([f[1] for f in feature_imps[0:5]]))
        print("-----\n")

        k += 1
