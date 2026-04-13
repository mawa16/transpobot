-- ============================================================
--  TranspoBot — Base de données MySQL
--  Projet GLSi L3 — ESP/UCAD
--  Version enrichie avec données de test réalistes
-- ============================================================

CREATE DATABASE IF NOT EXISTS transpobot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE transpobot;

-- ============================================================
--  TABLES
-- ============================================================

-- Véhicules de la flotte
CREATE TABLE vehicules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    immatriculation VARCHAR(20) NOT NULL UNIQUE,
    type ENUM('bus','minibus','taxi') NOT NULL,
    capacite INT NOT NULL,
    statut ENUM('actif','maintenance','hors_service') DEFAULT 'actif',
    kilometrage INT DEFAULT 0,
    date_acquisition DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chauffeurs employés
CREATE TABLE chauffeurs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(20),
    numero_permis VARCHAR(30) UNIQUE NOT NULL,
    categorie_permis VARCHAR(5),
    disponibilite BOOLEAN DEFAULT TRUE,
    vehicule_id INT,
    date_embauche DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicule_id) REFERENCES vehicules(id)
);

-- Lignes de transport
CREATE TABLE lignes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    nom VARCHAR(100),
    origine VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    distance_km DECIMAL(6,2),
    duree_minutes INT
);

-- Tarifs par ligne et type de client
CREATE TABLE tarifs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ligne_id INT NOT NULL,
    type_client ENUM('normal','etudiant','senior') DEFAULT 'normal',
    prix DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (ligne_id) REFERENCES lignes(id)
);

-- Trajets effectués
CREATE TABLE trajets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ligne_id INT NOT NULL,
    chauffeur_id INT NOT NULL,
    vehicule_id INT NOT NULL,
    date_heure_depart DATETIME NOT NULL,
    date_heure_arrivee DATETIME,
    statut ENUM('planifie','en_cours','termine','annule') DEFAULT 'planifie',
    nb_passagers INT DEFAULT 0,
    recette DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ligne_id) REFERENCES lignes(id),
    FOREIGN KEY (chauffeur_id) REFERENCES chauffeurs(id),
    FOREIGN KEY (vehicule_id) REFERENCES vehicules(id)
);

-- Incidents signalés
CREATE TABLE incidents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trajet_id INT NOT NULL,
    type ENUM('panne','accident','retard','autre') NOT NULL,
    description TEXT,
    gravite ENUM('faible','moyen','grave') DEFAULT 'faible',
    date_incident DATETIME NOT NULL,
    resolu BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trajet_id) REFERENCES trajets(id)
);

-- ============================================================
--  DONNÉES DE TEST
-- ============================================================

-- 10 véhicules variés
INSERT INTO vehicules (immatriculation, type, capacite, statut, kilometrage, date_acquisition) VALUES
('DK-1234-AB', 'bus',     60, 'actif',        45000,  '2021-03-15'),
('DK-5678-CD', 'minibus', 25, 'actif',        32000,  '2022-06-01'),
('DK-9012-EF', 'bus',     60, 'maintenance',  78000,  '2019-11-20'),
('DK-3456-GH', 'taxi',     5, 'actif',       120000,  '2020-01-10'),
('DK-7890-IJ', 'minibus', 25, 'actif',        15000,  '2023-09-05'),
('DK-2345-KL', 'bus',     60, 'actif',        52000,  '2021-07-22'),
('DK-6789-MN', 'taxi',     5, 'hors_service', 200000, '2017-05-30'),
('DK-0123-OP', 'minibus', 30, 'actif',        28000,  '2022-11-14'),
('DK-4567-QR', 'bus',     55, 'actif',        61000,  '2020-08-09'),
('DK-8901-ST', 'minibus', 20, 'maintenance',  43000,  '2021-12-01');

-- 10 chauffeurs
INSERT INTO chauffeurs (nom, prenom, telephone, numero_permis, categorie_permis, disponibilite, vehicule_id, date_embauche) VALUES
('DIOP',    'Mamadou',  '+221771234567', 'P-2019-001', 'D',  TRUE,  1,    '2019-04-01'),
('FALL',    'Ibrahima', '+221772345678', 'P-2020-002', 'D',  TRUE,  2,    '2020-07-15'),
('NDIAYE',  'Fatou',    '+221773456789', 'P-2021-003', 'B',  TRUE,  4,    '2021-02-01'),
('SECK',    'Ousmane',  '+221774567890', 'P-2022-004', 'D',  TRUE,  5,    '2022-10-20'),
('BA',      'Aminata',  '+221775678901', 'P-2023-005', 'D',  FALSE, NULL, '2023-01-10'),
('MBAYE',   'Cheikh',   '+221776789012', 'P-2019-006', 'D',  TRUE,  6,    '2019-09-01'),
('GUEYE',   'Rokhaya',  '+221777890123', 'P-2021-007', 'D',  TRUE,  8,    '2021-05-20'),
('SARR',    'Modou',    '+221778901234', 'P-2020-008', 'D',  TRUE,  9,    '2020-03-11'),
('DIOUF',   'Ndèye',    '+221779012345', 'P-2022-009', 'B',  FALSE, NULL, '2022-08-05'),
('THIAM',   'Pape',     '+221770123456', 'P-2023-010', 'D',  TRUE,  NULL, '2023-06-15');

-- 4 lignes
INSERT INTO lignes (code, nom, origine, destination, distance_km, duree_minutes) VALUES
('L1', 'Ligne Dakar-Thiès',      'Dakar',       'Thiès',   70.5, 90),
('L2', 'Ligne Dakar-Mbour',      'Dakar',       'Mbour',   82.0, 120),
('L3', 'Ligne Centre-Banlieue',  'Plateau',     'Pikine',  15.0, 45),
('L4', 'Ligne Aéroport',         'Centre-ville','AIBD',    45.0, 60);

-- Tarifs
INSERT INTO tarifs (ligne_id, type_client, prix) VALUES
(1, 'normal',   2500), (1, 'etudiant', 1500), (1, 'senior', 1800),
(2, 'normal',   3000), (2, 'etudiant', 1800), (2, 'senior', 2200),
(3, 'normal',    500), (3, 'etudiant',  300), (3, 'senior',  400),
(4, 'normal',   5000), (4, 'etudiant', 3000), (4, 'senior', 4000);

-- ============================================================
--  TRAJETS — Février et Mars 2026 (données réalistes)
-- ============================================================
INSERT INTO trajets (ligne_id, chauffeur_id, vehicule_id, date_heure_depart, date_heure_arrivee, statut, nb_passagers, recette) VALUES
-- Février 2026
(1, 1, 1, '2026-02-02 06:00:00', '2026-02-02 07:30:00', 'termine', 55, 137500),
(2, 2, 2, '2026-02-03 07:00:00', '2026-02-03 09:00:00', 'termine', 20,  60000),
(3, 3, 4, '2026-02-04 07:30:00', '2026-02-04 08:15:00', 'termine',  4,   2000),
(4, 6, 6, '2026-02-05 08:00:00', '2026-02-05 09:00:00', 'termine', 30, 150000),
(1, 7, 8, '2026-02-06 06:00:00', '2026-02-06 07:30:00', 'termine', 28,  70000),
(3, 4, 5, '2026-02-07 07:30:00', '2026-02-07 08:15:00', 'termine', 22,  11000),
(2, 8, 9, '2026-02-10 07:00:00', '2026-02-10 09:00:00', 'termine', 35, 105000),
(1, 1, 1, '2026-02-11 06:00:00', '2026-02-11 07:30:00', 'termine', 50, 125000),
(4, 2, 2, '2026-02-12 09:00:00', '2026-02-12 10:00:00', 'termine', 18,  90000),
(3, 6, 6, '2026-02-14 07:30:00', '2026-02-14 08:15:00', 'termine', 25,  12500),
(1, 8, 9, '2026-02-17 06:00:00', '2026-02-17 07:30:00', 'termine', 60, 150000),
(2, 7, 8, '2026-02-18 07:00:00', '2026-02-18 09:00:00', 'termine', 22,  66000),
(4, 4, 5, '2026-02-20 08:00:00', '2026-02-20 09:00:00', 'termine', 12,  60000),
(1, 1, 1, '2026-02-24 06:00:00', '2026-02-24 07:30:00', 'termine', 58, 145000),
(3, 3, 4, '2026-02-25 07:30:00', '2026-02-25 08:15:00', 'annule',   0,      0),
-- Mars 2026
(1, 1, 1, '2026-03-01 06:00:00', '2026-03-01 07:30:00', 'termine', 55, 137500),
(1, 2, 2, '2026-03-01 08:00:00', '2026-03-01 09:30:00', 'termine', 20,  50000),
(2, 3, 4, '2026-03-02 07:00:00', '2026-03-02 09:00:00', 'termine',  4,  12000),
(3, 4, 5, '2026-03-05 07:30:00', '2026-03-05 08:15:00', 'termine', 22,  11000),
(1, 1, 1, '2026-03-10 06:00:00', '2026-03-10 07:30:00', 'termine', 58, 145000),
(4, 2, 2, '2026-03-12 09:00:00', '2026-03-12 10:00:00', 'termine', 18,  90000),
(2, 6, 6, '2026-03-13 07:00:00', '2026-03-13 09:00:00', 'termine', 40, 120000),
(3, 7, 8, '2026-03-14 07:30:00', '2026-03-14 08:15:00', 'termine', 18,   9000),
(1, 8, 9, '2026-03-15 06:00:00', '2026-03-15 07:30:00', 'termine', 52, 130000),
(4, 4, 5, '2026-03-17 08:00:00', '2026-03-17 09:00:00', 'termine', 25, 125000),
(2, 1, 1, '2026-03-18 07:00:00', '2026-03-18 09:00:00', 'termine', 45, 135000),
(3, 6, 6, '2026-03-19 07:30:00', '2026-03-19 08:15:00', 'termine', 20,  10000),
(1, 5, 1, '2026-03-20 06:00:00', NULL,                  'en_cours', 45, 112500),
(4, 2, 2, '2026-03-20 09:00:00', NULL,                  'en_cours', 10,  50000),
(1, 7, 8, '2026-03-21 06:00:00', '2026-03-21 07:30:00', 'termine', 48, 120000),
(2, 8, 9, '2026-03-22 07:00:00', '2026-03-22 09:00:00', 'termine', 30,  90000),
(3, 3, 4, '2026-03-24 07:30:00', '2026-03-24 08:15:00', 'termine', 15,   7500),
(4, 6, 6, '2026-03-25 08:00:00', '2026-03-25 09:00:00', 'termine', 22, 110000),
(1, 4, 5, '2026-03-27 06:00:00', '2026-03-27 07:30:00', 'annule',   0,      0),
-- Semaine en cours (avril 2026)
(1, 1, 1, '2026-04-01 06:00:00', '2026-04-01 07:30:00', 'termine', 55, 137500),
(2, 6, 6, '2026-04-01 07:00:00', '2026-04-01 09:00:00', 'termine', 38, 114000),
(3, 7, 8, '2026-04-02 07:30:00', '2026-04-02 08:15:00', 'termine', 20,  10000),
(4, 2, 2, '2026-04-03 08:00:00', '2026-04-03 09:00:00', 'termine', 15,  75000),
(1, 8, 9, '2026-04-04 06:00:00', '2026-04-04 07:30:00', 'termine', 50, 125000),
(2, 4, 5, '2026-04-05 07:00:00', NULL,                  'en_cours', 30,  90000);

-- ============================================================
--  INCIDENTS variés
-- ============================================================
INSERT INTO incidents (trajet_id, type, description, gravite, date_incident, resolu) VALUES
(2,  'retard',   'Embouteillage au centre-ville',           'faible', '2026-02-03 08:45:00', TRUE),
(3,  'panne',    'Crevaison pneu avant droit',              'moyen',  '2026-02-04 07:30:00', TRUE),
(7,  'retard',   'Route barrée déviation Mbour',            'faible', '2026-02-10 08:00:00', TRUE),
(10, 'autre',    'Passager malaise à bord',                 'moyen',  '2026-02-14 07:50:00', TRUE),
(12, 'panne',    'Problème moteur surchauffe',              'grave',  '2026-02-18 08:20:00', TRUE),
(17, 'retard',   'Embouteillage au centre-ville',           'faible', '2026-03-01 08:45:00', TRUE),
(18, 'panne',    'Crevaison pneu avant droit',              'moyen',  '2026-03-02 07:30:00', TRUE),
(22, 'retard',   'Travaux sur la route de Mbour',           'faible', '2026-03-13 07:45:00', TRUE),
(24, 'accident', 'Accrochage léger feu rouge Plateau',      'moyen',  '2026-03-15 06:50:00', FALSE),
(26, 'retard',   'Grève partielle transporteurs',           'moyen',  '2026-03-18 07:30:00', TRUE),
(28, 'panne',    'Batterie déchargée démarrage impossible', 'faible', '2026-03-20 05:55:00', FALSE),
(30, 'accident', 'Accrochage léger au rond-point',          'grave',  '2026-03-12 09:20:00', FALSE),
(33, 'retard',   'Manifestation boulevard principal',       'moyen',  '2026-03-24 07:40:00', TRUE),
(38, 'panne',    'Fuite hydraulique frein avant',           'grave',  '2026-04-01 06:40:00', FALSE),
(40, 'retard',   'Embouteillage sortie Dakar',              'faible', '2026-04-03 08:15:00', TRUE);
