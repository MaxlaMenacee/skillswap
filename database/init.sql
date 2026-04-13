-- SkillSwap — Script d'initialisation de la base de données
-- Base : SQLite (sobre, sans serveur dédié)

-- Table des compétences (tags normalisés)
CREATE TABLE IF NOT EXISTS competence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle TEXT NOT NULL UNIQUE
);

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS utilisateur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'utilisateur' CHECK(role IN ('utilisateur', 'administrateur')),
    date_inscription TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Compétences offertes par un utilisateur
CREATE TABLE IF NOT EXISTS competence_offerte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id INTEGER NOT NULL,
    competence_id INTEGER NOT NULL,
    FOREIGN KEY (utilisateur_id) REFERENCES utilisateur(id) ON DELETE CASCADE,
    FOREIGN KEY (competence_id) REFERENCES competence(id) ON DELETE CASCADE,
    UNIQUE(utilisateur_id, competence_id)
);

-- Compétences cherchées par un utilisateur
CREATE TABLE IF NOT EXISTS competence_cherchee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id INTEGER NOT NULL,
    competence_id INTEGER NOT NULL,
    FOREIGN KEY (utilisateur_id) REFERENCES utilisateur(id) ON DELETE CASCADE,
    FOREIGN KEY (competence_id) REFERENCES competence(id) ON DELETE CASCADE,
    UNIQUE(utilisateur_id, competence_id)
);

-- Sessions d'échange
CREATE TABLE IF NOT EXISTS session_echange (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_1_id INTEGER NOT NULL,
    utilisateur_2_id INTEGER NOT NULL,
    competence_id INTEGER NOT NULL,
    date_souhaitee TEXT NOT NULL,
    duree_estimee INTEGER NOT NULL DEFAULT 60,
    statut TEXT NOT NULL DEFAULT 'proposé' CHECK(statut IN ('proposé', 'confirmé', 'terminé', 'annulé')),
    notes TEXT,
    date_creation TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (utilisateur_1_id) REFERENCES utilisateur(id) ON DELETE CASCADE,
    FOREIGN KEY (utilisateur_2_id) REFERENCES utilisateur(id) ON DELETE CASCADE,
    FOREIGN KEY (competence_id) REFERENCES competence(id) ON DELETE CASCADE
);

-- Index sur les colonnes fréquemment interrogées
CREATE INDEX IF NOT EXISTS idx_utilisateur_email ON utilisateur(email);
CREATE INDEX IF NOT EXISTS idx_comp_offerte_user ON competence_offerte(utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_comp_cherchee_user ON competence_cherchee(utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_session_user1 ON session_echange(utilisateur_1_id);
CREATE INDEX IF NOT EXISTS idx_session_user2 ON session_echange(utilisateur_2_id);
CREATE INDEX IF NOT EXISTS idx_session_statut ON session_echange(statut);

-- Données initiales : compétences populaires
INSERT OR IGNORE INTO competence (libelle) VALUES
    ('Python'),
    ('JavaScript'),
    ('SQL'),
    ('HTML/CSS'),
    ('Java'),
    ('C/C++'),
    ('Photoshop'),
    ('Excel'),
    ('Anglais'),
    ('Espagnol'),
    ('Allemand'),
    ('Guitare'),
    ('Piano'),
    ('Mathématiques'),
    ('Physique'),
    ('Rédaction'),
    ('Prise de parole'),
    ('Git/GitHub'),
    ('Linux'),
    ('Réseaux');

-- Utilisateur admin par défaut (mot de passe : Admin123!)
-- Le hash sera généré par l'application au premier lancement
