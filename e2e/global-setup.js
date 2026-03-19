const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const rootDir = path.resolve(__dirname, '..');
const storageStatePath = path.join(__dirname, '.auth', 'user.json');
const freeStorageStatePath = path.join(__dirname, '.auth', 'free-user.json');
const upgradeStorageStatePath = path.join(__dirname, '.auth', 'upgrade-user.json');
const adminStorageStatePath = path.join(__dirname, '.auth', 'admin-user.json');
const sqliteUrl = 'sqlite:///c:/Users/LPLOO/Documents/CV Projects/PredictMyGrade-main/db.sqlite3';

function runDjangoScript(script) {
  return execFileSync(
    'python',
    ['manage.py', 'shell', '-c', script],
    {
      cwd: rootDir,
      encoding: 'utf8',
      env: {
        ...process.env,
        DJANGO_SECRET_KEY: 'dev-secret-key',
        DATABASE_URL: sqliteUrl,
        DJANGO_DEBUG: 'true',
        DJANGO_ALLOWED_HOSTS: '127.0.0.1,localhost,testserver',
        BILLING_MOCK_MODE: '1',
      },
    },
  ).trim();
}

module.exports = async () => {
  fs.mkdirSync(path.dirname(storageStatePath), { recursive: true });

  const script = [
    'from datetime import date',
    'from django.contrib.auth import get_user_model',
    'from django.contrib.sessions.backends.db import SessionStore',
    'from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY',
    'from core.models import Module, StudyPlan',
    'User = get_user_model()',
    "premium_user, _ = User.objects.get_or_create(username='qauser', defaults={'email': 'qa@example.com'})",
    "premium_user.set_password('pass1234')",
    'premium_user.save()',
    'premium_user.profile.set_premium(True)',
    "Module.objects.get_or_create(user=premium_user, name='QA Module', level='UNI', defaults={'credits': 20, 'grade_percent': 72, 'completion_percent': 80})",
    "StudyPlan.objects.get_or_create(user=premium_user, title='QA Session', date=date.today(), defaults={'duration_hours': 2})",
    "free_user, _ = User.objects.get_or_create(username='qafree', defaults={'email': 'qafree@example.com'})",
    "free_user.set_password('pass1234')",
    'free_user.save()',
    'free_user.profile.set_premium(False)',
    "upgrade_user, _ = User.objects.get_or_create(username='qaupgrade', defaults={'email': 'qaupgrade@example.com'})",
    "upgrade_user.set_password('pass1234')",
    'upgrade_user.save()',
    'upgrade_user.profile.set_premium(False)',
    "toggle_target, _ = User.objects.get_or_create(username='qatoggle', defaults={'email': 'qatoggle@example.com'})",
    "toggle_target.set_password('pass1234')",
    'toggle_target.save()',
    'toggle_target.profile.set_premium(False)',
    "admin_user, _ = User.objects.get_or_create(username='qaadmin', defaults={'email': 'qaadmin@example.com', 'is_staff': True, 'is_superuser': True})",
    "admin_user.set_password('pass1234')",
    'admin_user.is_staff = True',
    'admin_user.is_superuser = True',
    'admin_user.save()',
    'premium_session = SessionStore()',
    "premium_session[SESSION_KEY] = str(premium_user.pk)",
    "premium_session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'",
    'premium_session[HASH_SESSION_KEY] = premium_user.get_session_auth_hash()',
    'premium_session.save()',
    'free_session = SessionStore()',
    "free_session[SESSION_KEY] = str(free_user.pk)",
    "free_session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'",
    'free_session[HASH_SESSION_KEY] = free_user.get_session_auth_hash()',
    'free_session.save()',
    'upgrade_session = SessionStore()',
    "upgrade_session[SESSION_KEY] = str(upgrade_user.pk)",
    "upgrade_session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'",
    'upgrade_session[HASH_SESSION_KEY] = upgrade_user.get_session_auth_hash()',
    'upgrade_session.save()',
    'admin_session = SessionStore()',
    "admin_session[SESSION_KEY] = str(admin_user.pk)",
    "admin_session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'",
    'admin_session[HASH_SESSION_KEY] = admin_user.get_session_auth_hash()',
    'admin_session.save()',
    "print(f'{premium_session.session_key}|{free_session.session_key}|{upgrade_session.session_key}|{admin_session.session_key}')",
  ].join('; ');

  const [premiumSessionKey, freeSessionKey, upgradeSessionKey, adminSessionKey] = runDjangoScript(script).split(/\r?\n/).pop().split('|');

  const storageState = {
    cookies: [
      {
        name: 'sessionid',
        value: premiumSessionKey,
        domain: '127.0.0.1',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ],
    origins: [],
  };

  const freeStorageState = {
    cookies: [
      {
        name: 'sessionid',
        value: freeSessionKey,
        domain: '127.0.0.1',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ],
    origins: [],
  };

  const adminStorageState = {
    cookies: [
      {
        name: 'sessionid',
        value: adminSessionKey,
        domain: '127.0.0.1',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ],
    origins: [],
  };

  const upgradeStorageState = {
    cookies: [
      {
        name: 'sessionid',
        value: upgradeSessionKey,
        domain: '127.0.0.1',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ],
    origins: [],
  };

  fs.writeFileSync(storageStatePath, JSON.stringify(storageState, null, 2));
  fs.writeFileSync(freeStorageStatePath, JSON.stringify(freeStorageState, null, 2));
  fs.writeFileSync(upgradeStorageStatePath, JSON.stringify(upgradeStorageState, null, 2));
  fs.writeFileSync(adminStorageStatePath, JSON.stringify(adminStorageState, null, 2));
};
