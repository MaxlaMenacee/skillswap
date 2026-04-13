"""
SkillSwap — Plateforme de troc de compétences entre étudiants
Backend Flask avec SQLite — Éco-conception web (Green IT)
"""

import os
import sqlite3
import math
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort
)
from flask_bcrypt import Bcrypt

# --- Configuration ---
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static')
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), '..', 'database', 'skillswap.db')
app.config['PER_PAGE'] = 20  # Pagination : max 20 résultats par page

bcrypt = Bcrypt(app)


# --- Base de données ---
def get_db():
    """Connexion à la BDD avec mise en cache dans le contexte de requête."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")  # Performance en écriture
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialise la BDD à partir du script SQL."""
    db = get_db()
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'init.sql')
    with open(sql_path, 'r') as f:
        db.executescript(f.read())
    # Créer l'admin par défaut s'il n'existe pas
    admin = db.execute("SELECT id FROM utilisateur WHERE email = ?", ('admin@skillswap.fr',)).fetchone()
    if not admin:
        hashed = bcrypt.generate_password_hash('Admin123!').decode('utf-8')
        db.execute(
            "INSERT INTO utilisateur (nom, prenom, email, mot_de_passe, role) VALUES (?, ?, ?, ?, ?)",
            ('Admin', 'SkillSwap', 'admin@skillswap.fr', hashed, 'administrateur')
        )
        db.commit()


@app.cli.command('init-db')
def init_db_command():
    init_db()
    print('Base de données initialisée.')


# --- Décorateurs d'authentification ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('login'))
        if session.get('user_role') != 'administrateur':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# --- Contexte global pour les templates ---
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        db = get_db()
        user = db.execute("SELECT id, nom, prenom, role FROM utilisateur WHERE id = ?",
                          (session['user_id'],)).fetchone()
    return {'current_user': user}


# --- Utilitaires ---
def paginate(query, params, page, per_page=None):
    """Pagine une requête SQL. Retourne (résultats, total_pages, page_courante)."""
    if per_page is None:
        per_page = app.config['PER_PAGE']
    db = get_db()
    # Compter le total
    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = db.execute(count_query, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    results = db.execute(f"{query} LIMIT ? OFFSET ?", params + (per_page, offset)).fetchall()
    return results, total_pages, page


def validate_email(email):
    """Validation basique du format email."""
    return '@' in email and '.' in email.split('@')[-1] and len(email) <= 254


def validate_password(password):
    """Mot de passe : min 8 caractères, 1 majuscule, 1 chiffre."""
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True


# =============================================
#  ROUTES — Pages publiques
# =============================================

@app.route('/')
def index():
    db = get_db()
    # Récupérer les compétences populaires (celles les plus offertes)
    competences = db.execute("""
        SELECT c.id, c.libelle, COUNT(co.id) AS nb
        FROM competence c
        LEFT JOIN competence_offerte co ON c.id = co.competence_id
        GROUP BY c.id
        ORDER BY nb DESC
        LIMIT 8
    """).fetchall()
    # Profils récents (les 6 derniers inscrits)
    profils = db.execute("""
        SELECT u.id, u.nom, u.prenom, u.date_inscription
        FROM utilisateur u
        WHERE u.role = 'utilisateur'
        ORDER BY u.date_inscription DESC
        LIMIT 6
    """).fetchall()
    # Charger les compétences offertes/cherchées pour chaque profil
    profils_enrichis = []
    for p in profils:
        offertes = db.execute("""
            SELECT c.libelle FROM competence c
            JOIN competence_offerte co ON c.id = co.competence_id
            WHERE co.utilisateur_id = ?
            LIMIT 3
        """, (p['id'],)).fetchall()
        cherchees = db.execute("""
            SELECT c.libelle FROM competence c
            JOIN competence_cherchee cc ON c.id = cc.competence_id
            WHERE cc.utilisateur_id = ?
            LIMIT 3
        """, (p['id'],)).fetchall()
        profils_enrichis.append({
            'id': p['id'],
            'nom': p['nom'],
            'prenom': p['prenom'],
            'offertes': [o['libelle'] for o in offertes],
            'cherchees': [c['libelle'] for c in cherchees],
        })
    return render_template('index.html', competences=competences, profils=profils_enrichis)


@app.route('/parcourir')
def parcourir():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    filtre = request.args.get('competence', '', type=str).strip()

    if filtre:
        query = """
            SELECT DISTINCT u.id, u.nom, u.prenom, u.date_inscription
            FROM utilisateur u
            JOIN competence_offerte co ON u.id = co.utilisateur_id
            JOIN competence c ON co.competence_id = c.id
            WHERE u.role = 'utilisateur' AND c.libelle LIKE ?
            ORDER BY u.date_inscription DESC
        """
        params = (f'%{filtre}%',)
    else:
        query = """
            SELECT u.id, u.nom, u.prenom, u.date_inscription
            FROM utilisateur u
            WHERE u.role = 'utilisateur'
            ORDER BY u.date_inscription DESC
        """
        params = ()

    utilisateurs, total_pages, page = paginate(query, params, page)

    # Enrichir avec compétences
    resultats = []
    for u in utilisateurs:
        offertes = db.execute("""
            SELECT c.libelle FROM competence c
            JOIN competence_offerte co ON c.id = co.competence_id
            WHERE co.utilisateur_id = ? LIMIT 5
        """, (u['id'],)).fetchall()
        cherchees = db.execute("""
            SELECT c.libelle FROM competence c
            JOIN competence_cherchee cc ON c.id = cc.competence_id
            WHERE cc.utilisateur_id = ? LIMIT 5
        """, (u['id'],)).fetchall()
        resultats.append({
            'id': u['id'],
            'nom': u['nom'],
            'prenom': u['prenom'],
            'offertes': [o['libelle'] for o in offertes],
            'cherchees': [c['libelle'] for c in cherchees],
        })

    competences = db.execute("SELECT libelle FROM competence ORDER BY libelle").fetchall()

    return render_template('parcourir.html',
                           utilisateurs=resultats,
                           competences=competences,
                           filtre=filtre,
                           page=page,
                           total_pages=total_pages)


# =============================================
#  ROUTES — Authentification
# =============================================

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('mot_de_passe', '')
        confirm = request.form.get('confirm_mot_de_passe', '')

        # Validation serveur
        errors = []
        if not nom or not prenom:
            errors.append('Nom et prénom requis.')
        if not validate_email(email):
            errors.append('Format email invalide.')
        if not validate_password(password):
            errors.append('Mot de passe : min. 8 caractères, 1 majuscule, 1 chiffre.')
        if password != confirm:
            errors.append('Les mots de passe ne correspondent pas.')

        db = get_db()
        existing = db.execute("SELECT id FROM utilisateur WHERE email = ?", (email,)).fetchone()
        if existing:
            errors.append('Cet email est déjà utilisé.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('inscription.html', nom=nom, prenom=prenom, email=email)

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        db.execute(
            "INSERT INTO utilisateur (nom, prenom, email, mot_de_passe) VALUES (?, ?, ?, ?)",
            (nom, prenom, email, hashed)
        )
        db.commit()

        user = db.execute("SELECT id, role FROM utilisateur WHERE email = ?", (email,)).fetchone()
        session['user_id'] = user['id']
        session['user_role'] = user['role']
        flash('Compte créé avec succès.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('inscription.html')


@app.route('/connexion', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('mot_de_passe', '')

        db = get_db()
        user = db.execute("SELECT id, mot_de_passe, role FROM utilisateur WHERE email = ?",
                          (email,)).fetchone()

        if user and bcrypt.check_password_hash(user['mot_de_passe'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            flash('Connexion réussie.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou mot de passe incorrect.', 'error')
            return render_template('login.html', email=email)

    return render_template('login.html')


@app.route('/deconnexion')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'success')
    return redirect(url_for('index'))


# =============================================
#  ROUTES — Tableau de bord utilisateur
# =============================================

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    uid = session['user_id']
    user = db.execute("SELECT id, nom, prenom, email, date_inscription FROM utilisateur WHERE id = ?",
                      (uid,)).fetchone()

    offertes = db.execute("""
        SELECT c.id, c.libelle FROM competence c
        JOIN competence_offerte co ON c.id = co.competence_id
        WHERE co.utilisateur_id = ?
    """, (uid,)).fetchall()

    cherchees = db.execute("""
        SELECT c.id, c.libelle FROM competence c
        JOIN competence_cherchee cc ON c.id = cc.competence_id
        WHERE cc.utilisateur_id = ?
    """, (uid,)).fetchall()

    sessions = db.execute("""
        SELECT se.id, se.date_souhaitee, se.duree_estimee, se.statut, se.notes,
               c.libelle AS competence,
               CASE WHEN se.utilisateur_1_id = ? THEN u2.prenom || ' ' || u2.nom
                    ELSE u1.prenom || ' ' || u1.nom END AS partenaire,
               CASE WHEN se.utilisateur_1_id = ? THEN u2.id ELSE u1.id END AS partenaire_id
        FROM session_echange se
        JOIN utilisateur u1 ON se.utilisateur_1_id = u1.id
        JOIN utilisateur u2 ON se.utilisateur_2_id = u2.id
        JOIN competence c ON se.competence_id = c.id
        WHERE se.utilisateur_1_id = ? OR se.utilisateur_2_id = ?
        ORDER BY se.date_creation DESC
        LIMIT 20
    """, (uid, uid, uid, uid)).fetchall()

    return render_template('dashboard.html', user=user, offertes=offertes,
                           cherchees=cherchees, sessions=sessions)


# =============================================
#  ROUTES — CRUD Utilisateur (profil)
# =============================================

@app.route('/profil/modifier', methods=['GET', 'POST'])
@login_required
def modifier_profil():
    db = get_db()
    uid = session['user_id']

    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip().lower()

        errors = []
        if not nom or not prenom:
            errors.append('Nom et prénom requis.')
        if not validate_email(email):
            errors.append('Format email invalide.')

        existing = db.execute("SELECT id FROM utilisateur WHERE email = ? AND id != ?",
                              (email, uid)).fetchone()
        if existing:
            errors.append('Cet email est déjà utilisé.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            db.execute("UPDATE utilisateur SET nom = ?, prenom = ?, email = ? WHERE id = ?",
                       (nom, prenom, email, uid))
            db.commit()
            flash('Profil mis à jour.', 'success')
            return redirect(url_for('dashboard'))

    user = db.execute("SELECT id, nom, prenom, email FROM utilisateur WHERE id = ?", (uid,)).fetchone()
    return render_template('modifier_profil.html', user=user)


@app.route('/profil/competences', methods=['GET', 'POST'])
@login_required
def gerer_competences():
    db = get_db()
    uid = session['user_id']

    if request.method == 'POST':
        offertes_ids = request.form.getlist('offertes')
        cherchees_ids = request.form.getlist('cherchees')

        # Supprimer les anciennes et insérer les nouvelles
        db.execute("DELETE FROM competence_offerte WHERE utilisateur_id = ?", (uid,))
        db.execute("DELETE FROM competence_cherchee WHERE utilisateur_id = ?", (uid,))

        for cid in offertes_ids:
            db.execute("INSERT OR IGNORE INTO competence_offerte (utilisateur_id, competence_id) VALUES (?, ?)",
                       (uid, int(cid)))
        for cid in cherchees_ids:
            db.execute("INSERT OR IGNORE INTO competence_cherchee (utilisateur_id, competence_id) VALUES (?, ?)",
                       (uid, int(cid)))
        db.commit()
        flash('Compétences mises à jour.', 'success')
        return redirect(url_for('dashboard'))

    competences = db.execute("SELECT id, libelle FROM competence ORDER BY libelle").fetchall()
    offertes_ids = [r['competence_id'] for r in
                    db.execute("SELECT competence_id FROM competence_offerte WHERE utilisateur_id = ?",
                               (uid,)).fetchall()]
    cherchees_ids = [r['competence_id'] for r in
                     db.execute("SELECT competence_id FROM competence_cherchee WHERE utilisateur_id = ?",
                                (uid,)).fetchall()]

    return render_template('gerer_competences.html', competences=competences,
                           offertes_ids=offertes_ids, cherchees_ids=cherchees_ids)


@app.route('/profil/supprimer', methods=['POST'])
@login_required
def supprimer_profil():
    db = get_db()
    uid = session['user_id']
    confirmation = request.form.get('confirmation', '')

    if confirmation != 'SUPPRIMER':
        flash('Tapez SUPPRIMER pour confirmer.', 'error')
        return redirect(url_for('dashboard'))

    db.execute("DELETE FROM utilisateur WHERE id = ?", (uid,))
    db.commit()
    session.clear()
    flash('Compte supprimé.', 'success')
    return redirect(url_for('index'))


@app.route('/profil/<int:user_id>')
def voir_profil(user_id):
    db = get_db()
    user = db.execute("SELECT id, nom, prenom, date_inscription FROM utilisateur WHERE id = ?",
                      (user_id,)).fetchone()
    if not user:
        abort(404)

    offertes = db.execute("""
        SELECT c.libelle FROM competence c
        JOIN competence_offerte co ON c.id = co.competence_id
        WHERE co.utilisateur_id = ?
    """, (user_id,)).fetchall()

    cherchees = db.execute("""
        SELECT c.libelle FROM competence c
        JOIN competence_cherchee cc ON c.id = cc.competence_id
        WHERE cc.utilisateur_id = ?
    """, (user_id,)).fetchall()

    return render_template('voir_profil.html', user=user,
                           offertes=offertes, cherchees=cherchees)


# =============================================
#  ROUTES — CRUD Sessions d'échange
# =============================================

@app.route('/sessions/nouvelle/<int:partenaire_id>', methods=['GET', 'POST'])
@login_required
def nouvelle_session(partenaire_id):
    db = get_db()
    uid = session['user_id']

    if uid == partenaire_id:
        flash('Vous ne pouvez pas créer une session avec vous-même.', 'error')
        return redirect(url_for('parcourir'))

    partenaire = db.execute("SELECT id, nom, prenom FROM utilisateur WHERE id = ?",
                            (partenaire_id,)).fetchone()
    if not partenaire:
        abort(404)

    if request.method == 'POST':
        competence_id = request.form.get('competence_id', type=int)
        date_souhaitee = request.form.get('date_souhaitee', '').strip()
        duree = request.form.get('duree_estimee', 60, type=int)
        notes = request.form.get('notes', '').strip()

        errors = []
        if not competence_id:
            errors.append('Sélectionnez une compétence.')
        if not date_souhaitee:
            errors.append('Date requise.')
        if duree < 15 or duree > 240:
            errors.append('Durée : entre 15 et 240 minutes.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            db.execute("""
                INSERT INTO session_echange
                (utilisateur_1_id, utilisateur_2_id, competence_id, date_souhaitee, duree_estimee, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, partenaire_id, competence_id, date_souhaitee, duree, notes or None))
            db.commit()
            flash('Session proposée.', 'success')
            return redirect(url_for('dashboard'))

    # Compétences offertes par le partenaire
    competences = db.execute("""
        SELECT c.id, c.libelle FROM competence c
        JOIN competence_offerte co ON c.id = co.competence_id
        WHERE co.utilisateur_id = ?
        ORDER BY c.libelle
    """, (partenaire_id,)).fetchall()

    return render_template('nouvelle_session.html', partenaire=partenaire,
                           competences=competences)


@app.route('/sessions/<int:session_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_session(session_id):
    db = get_db()
    uid = session['user_id']

    se = db.execute("""
        SELECT se.*, c.libelle AS competence_libelle
        FROM session_echange se
        JOIN competence c ON se.competence_id = c.id
        WHERE se.id = ?
    """, (session_id,)).fetchone()

    if not se:
        abort(404)

    # Seuls les participants peuvent modifier
    if se['utilisateur_1_id'] != uid and se['utilisateur_2_id'] != uid:
        if session.get('user_role') != 'administrateur':
            abort(403)

    if request.method == 'POST':
        statut = request.form.get('statut', '').strip()
        date_souhaitee = request.form.get('date_souhaitee', '').strip()
        duree = request.form.get('duree_estimee', 60, type=int)
        notes = request.form.get('notes', '').strip()

        if statut not in ('proposé', 'confirmé', 'terminé', 'annulé'):
            flash('Statut invalide.', 'error')
        else:
            db.execute("""
                UPDATE session_echange
                SET statut = ?, date_souhaitee = ?, duree_estimee = ?, notes = ?
                WHERE id = ?
            """, (statut, date_souhaitee, duree, notes or None, session_id))
            db.commit()
            flash('Session mise à jour.', 'success')
            return redirect(url_for('dashboard'))

    return render_template('modifier_session.html', se=se)


@app.route('/sessions/<int:session_id>/supprimer', methods=['POST'])
@login_required
def supprimer_session(session_id):
    db = get_db()
    uid = session['user_id']

    se = db.execute("SELECT utilisateur_1_id, utilisateur_2_id FROM session_echange WHERE id = ?",
                    (session_id,)).fetchone()
    if not se:
        abort(404)

    is_admin = session.get('user_role') == 'administrateur'
    if se['utilisateur_1_id'] != uid and se['utilisateur_2_id'] != uid and not is_admin:
        abort(403)

    confirmation = request.form.get('confirmation', '')
    if confirmation != 'SUPPRIMER':
        flash('Tapez SUPPRIMER pour confirmer.', 'error')
        return redirect(url_for('modifier_session', session_id=session_id))

    db.execute("DELETE FROM session_echange WHERE id = ?", (session_id,))
    db.commit()
    flash('Session supprimée.', 'success')
    return redirect(url_for('dashboard'))


# =============================================
#  ROUTES — Administration
# =============================================

@app.route('/admin/utilisateurs')
@admin_required
def admin_utilisateurs():
    db = get_db()
    page = request.args.get('page', 1, type=int)

    query = "SELECT id, nom, prenom, email, role, date_inscription FROM utilisateur ORDER BY date_inscription DESC"
    utilisateurs, total_pages, page = paginate(query, (), page)

    return render_template('admin_utilisateurs.html',
                           utilisateurs=utilisateurs,
                           page=page,
                           total_pages=total_pages)


@app.route('/admin/utilisateurs/<int:user_id>/modifier', methods=['GET', 'POST'])
@admin_required
def admin_modifier_utilisateur(user_id):
    db = get_db()
    user = db.execute("SELECT id, nom, prenom, email, role FROM utilisateur WHERE id = ?",
                      (user_id,)).fetchone()
    if not user:
        abort(404)

    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'utilisateur')

        errors = []
        if not nom or not prenom:
            errors.append('Nom et prénom requis.')
        if not validate_email(email):
            errors.append('Format email invalide.')
        if role not in ('utilisateur', 'administrateur'):
            errors.append('Rôle invalide.')

        existing = db.execute("SELECT id FROM utilisateur WHERE email = ? AND id != ?",
                              (email, user_id)).fetchone()
        if existing:
            errors.append('Email déjà utilisé.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            db.execute("UPDATE utilisateur SET nom = ?, prenom = ?, email = ?, role = ? WHERE id = ?",
                       (nom, prenom, email, role, user_id))
            db.commit()
            flash('Utilisateur mis à jour.', 'success')
            return redirect(url_for('admin_utilisateurs'))

    return render_template('admin_modifier_utilisateur.html', user=user)


@app.route('/admin/utilisateurs/<int:user_id>/supprimer', methods=['POST'])
@admin_required
def admin_supprimer_utilisateur(user_id):
    db = get_db()

    if user_id == session['user_id']:
        flash('Vous ne pouvez pas supprimer votre propre compte admin.', 'error')
        return redirect(url_for('admin_utilisateurs'))

    confirmation = request.form.get('confirmation', '')
    if confirmation != 'SUPPRIMER':
        flash('Tapez SUPPRIMER pour confirmer.', 'error')
        return redirect(url_for('admin_utilisateurs'))

    db.execute("DELETE FROM utilisateur WHERE id = ?", (user_id,))
    db.commit()
    flash('Utilisateur supprimé.', 'success')
    return redirect(url_for('admin_utilisateurs'))


@app.route('/admin/sessions')
@admin_required
def admin_sessions():
    db = get_db()
    page = request.args.get('page', 1, type=int)

    query = """
        SELECT se.id, se.date_souhaitee, se.duree_estimee, se.statut,
               c.libelle AS competence,
               u1.prenom || ' ' || u1.nom AS proposant,
               u2.prenom || ' ' || u2.nom AS destinataire
        FROM session_echange se
        JOIN utilisateur u1 ON se.utilisateur_1_id = u1.id
        JOIN utilisateur u2 ON se.utilisateur_2_id = u2.id
        JOIN competence c ON se.competence_id = c.id
        ORDER BY se.date_creation DESC
    """
    sessions_list, total_pages, page = paginate(query, (), page)

    return render_template('admin_sessions.html',
                           sessions=sessions_list,
                           page=page,
                           total_pages=total_pages)


# =============================================
#  ROUTES — Pages d'erreur
# =============================================

@app.errorhandler(403)
def forbidden(e):
    return render_template('erreur.html', code=403, message='Accès interdit.'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('erreur.html', code=404, message='Page introuvable.'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('erreur.html', code=500, message='Erreur interne du serveur.'), 500


# =============================================
#  Lancement
# =============================================

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
