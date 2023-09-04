
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session, jsonify
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

bp = Blueprint('game', __name__)

import pandas as pd
import os
from datetime import datetime,timedelta
from numpy import random

def next_to_compare(show_list,compare):
    med_index=len(show_list)//2
    
    if compare=="Higher":
        new_rest_list=show_list[:med_index]
    else:
        new_rest_list=show_list[med_index+1:]
        
    
    return new_rest_list

category_ratings={"Good":[20/3,10],"Average":[10/3,20/3],"Bad":[0,10/3]}

@bp.route('/')
def index():
    db = get_db()
    shows_rating = db.execute(
        'SELECT *'
        ' FROM user'
    ).fetchall()

    if len(shows_rating)!=0:
        num_show_query='''
            SELECT title FROM shows
        '''

        good_show_query='''
            SELECT title FROM shows
            WHERE category="Good"
        '''

        average_show_query='''
            SELECT title FROM shows
            WHERE category="Average"
        '''

        bad_show_query='''
            SELECT title FROM shows
            WHERE category="Bad"
        '''

        num_shows=len([i for i in db.execute(num_show_query).fetchall()])
        num_good_shows=len([i for i in db.execute(good_show_query).fetchall()])
        num_average_shows=len([i for i in db.execute(average_show_query).fetchall()])
        num_bad_shows=len([i for i in db.execute(bad_show_query).fetchall()])

        if num_shows>1:
            results_query='''
                SELECT title, rating,
                    CASE WHEN category='Good' THEN
                        ROUND(CAST((?-(RANK() OVER (PARTITION BY category ORDER BY rating DESC))) AS REAL)*?/?+?,1)
                    WHEN category='Average' THEN
                        ROUND(CAST((?-(RANK() OVER (PARTITION BY category ORDER BY rating DESC))) AS REAL)*?/?+?,1)
                    ELSE ROUND(CAST((?-(RANK() OVER (PARTITION BY category ORDER BY rating DESC))) AS REAL)*?/?+?,1) END AS score,
                    category
                FROM shows
                WHERE user_id=?
                ORDER BY CASE
                WHEN category='Good' THEN 1
                WHEN category='Average' THEN 2
                WHEN category='Bad' THEN 3 END,rating DESC
            '''

            shows=db.execute(results_query,
                (num_good_shows+1,10/3,num_good_shows+1,20/3,
                 num_average_shows+1,10/3,num_average_shows+1,10/3,
                 num_bad_shows+1,10/3,num_bad_shows+1,0,
                 g.user['id'])
            ).fetchall()
        else:
            results_query='''
                SELECT title, rating, rating AS score,category
                FROM shows
                WHERE user_id=?
            '''
            shows=db.execute(results_query,
                (g.user['id'],)
            ).fetchall()

        return render_template('game/index.html', shows=shows)
    else:
        return render_template('game/index.html', shows=shows_rating)

@bp.route('/compare', methods=('GET', 'POST'))
@login_required
def compare():

    db = get_db()

    all_scores=db.execute(
        'SELECT title, rating'
        ' FROM shows'
        ' WHERE user_id=?'
        ' AND category=?'
        ' ORDER BY rating DESC',
        (g.user['id'],session['category'])
    ).fetchall()

    all_ratings=[i['rating'] for i in all_scores]

    show=session['title']
    category=session['category']
    
    compare_show=all_scores[session['med_show_index']]

    if request.method == 'POST' and request.form.get('compare') is not None:

        compare_val=request.form['compare']

        if compare_val=="Higher":
            new_range=session['length'][:session['med_show_index']]
        if compare_val=="Lower":
            new_range=session['length'][session['med_show_index']+1:]
        
        if len(new_range)==0:
            if compare_val=="Higher":
                if session['length'][0]==0:
                    high=10
                else:
                    high=all_ratings[session['length'][0]-1]
                low=all_ratings[session['length'][0]]
            if compare_val=="Lower":
                high=all_ratings[session['length'][-1]]
                if session['length'][-1]==len(all_scores)-1:
                    low=0
                else:
                    low=all_ratings[session['length'][-1]+1]

            get_db().execute(
                'INSERT INTO shows (title, rating, user_id, category)'
                ' VALUES (?, ?, ?, ?)',
                (show, (high+low)/2, g.user['id'], category)
            )

            db.commit()

            return redirect(url_for('game.index'))

        new_med_show_index=(max(new_range)-min(new_range))//2
        compare_show=all_scores[new_range[new_med_show_index]]

        session['med_show_index']=new_med_show_index
        session['length']=new_range


        return render_template('game/compare.html',show=show,compare_show=compare_show)

    return render_template('game/compare.html',show=show,compare_show=compare_show)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():

    db = get_db()

    if request.method == 'POST':

        title = request.form['title']
        category = request.form['category']
        session['title']=title
        session['category']=category

        rating_list=category_ratings[category]

        all_scores=db.execute(
            'SELECT title, rating'
            ' FROM shows'
            ' WHERE user_id=?'
            ' AND category=?',
            (g.user['id'],session['category'])
        ).fetchall()

        if len(all_scores)!=0:
            session['length']=[i for i in range(len(all_scores))]
            session['med_show_index']=(max(session['length'])-min(session['length']))//2
            return redirect(url_for('game.compare'))
        else:
            get_db().execute(
                'INSERT INTO shows (title, rating, user_id, category)'
                ' VALUES (?, ?, ?, ?)',
                (title, round((rating_list[0]+rating_list[1])/2,1), g.user['id'], category)
            )
            db.commit()
            return redirect(url_for('game.index'))

    return render_template('game/create.html')