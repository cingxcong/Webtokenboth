import requests
import uuid
"""
Pure web app: Telegram dependencies removed.
"""
import random
import threading
from flask import Flask, request, render_template_string, redirect, url_for, make_response, jsonify
import base64
import os
import re
import time
import random as _random
import json
import imaplib
import ssl
import email
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# User Config (from environment variables)
USER_EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', '').strip()
USER_EMAIL_APP_PASSWORD = os.getenv('EMAIL_APP_PASSWORD', '').strip()
USER_PORT = os.getenv('PORT', '10000').strip()
ADMIN_KEY = os.getenv('ADMIN_KEY', '').strip()
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '').strip()  # <--- Add this line!
ACCESS_KEY = os.getenv('ACCESS_KEY', '').strip()
ACCESS_KEYS = [k.strip() for k in os.getenv('ACCESS_KEYS', '').split(',') if k.strip()]
PRIVATE_MODE = os.getenv('PRIVATE_MODE', 'false').strip().lower() in ('1','true','yes','on')

# Configuration
apiurl = "https://api.classplusapp.com"

# Flask App
app = Flask("ITsGOLU")

# Jinja filters and privacy helpers
def mask_email_address(addr: str) -> str:
    try:
        local, _, domain = (addr or "").partition("@")
        if not local or not domain:
            return addr
        if len(local) <= 2:
            masked_local = local[0:1] + "*" * max(0, len(local)-1)
        else:
            masked_local = local[0] + "*" * (len(local)-2) + local[-1]
        return f"{masked_local}@{domain}"
    except Exception:
        return addr

def mask_emails_in_text(text: str) -> str:
    try:
        pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        return pattern.sub(lambda m: mask_email_address(m.group(0)), text or "")
    except Exception:
        return text

app.jinja_env.filters['mask_email'] = mask_email_address

def _gate_ok(req: request) -> bool:
    if not PRIVATE_MODE:
        return True
    key = req.args.get("access") or req.headers.get("x-access-key") or req.cookies.get("access")
    if not key:
        return False
    # Accept single ACCESS_KEY or any from ACCESS_KEYS
    if ACCESS_KEY and key == ACCESS_KEY:
        return True
    if ACCESS_KEYS and key in ACCESS_KEYS:
        return True
    return False

@app.route("/", methods=["GET"])
def home():
    if not _gate_ok(request):
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Access — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
      body { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
      .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); }
    </style>
  </head>
  <body class="min-h-screen flex items-center justify-center p-6">
    <div class="glass max-w-md w-full rounded-2xl p-8 shadow-2xl border border-slate-700">
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-sky-500/20 rounded-full mb-4">
          <i class="fas fa-lock text-sky-400 text-2xl"></i>
        </div>
        <h2 class="text-2xl font-bold text-white">Access Required</h2>
        <p class="text-slate-400 mt-2">Enter your access key to continue</p>
      </div>
      
      <form method="post" action="{{ url_for('access_gate') }}" class="space-y-6">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <i class="fas fa-key text-slate-500"></i>
          </div>
          <input 
            type="password" 
            name="access" 
            placeholder="Access key" 
            required
            class="w-full bg-slate-800/50 border border-slate-700 rounded-lg py-3 pl-10 pr-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
          />
        </div>
        
        <button 
          type="submit" 
          class="w-full bg-gradient-to-r from-sky-600 to-sky-500 hover:from-sky-500 hover:to-sky-400 text-white font-semibold py-3 px-4 rounded-lg transition-all duration-300 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500"
        >
          Continue
        </button>
      </form>
      
      <div class="mt-8 text-center">
        <p class="text-slate-500 text-sm">Private mode is enabled</p>
        <p class="text-slate-600 text-xs mt-2">© 2023 -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:- Premium</p>
      </div>
    </div>
  </body>
</html>
            """
        )
    
    # Admin login check
    admin_logged_in = request.cookies.get('admin_logged_in') == 'true'
    
    # Generate CSRF token
    csrf_token = str(uuid.uuid4())
    
    return render_template_string(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>-:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:- — Premium</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
      /* Popup Styles */
      .popup-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 50;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
      }
      
      .popup-overlay.active {
        opacity: 1;
        visibility: visible;
      }
      
      .popup-content {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 16px;
        padding: 32px;
        max-width: 500px;
        width: 90%;
        max-height: 90vh;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
        transform: scale(0.9);
        transition: transform 0.3s ease;
        position: relative;
        overflow: hidden;
      }
      
      .popup-overlay.active .popup-content {
        transform: scale(1);
      }
      
      .popup-close {
        position: absolute;
        top: 16px;
        right: 16px;
        background: none;
        border: none;
        color: #94a3b8;
        cursor: pointer;
        font-size: 24px;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: all 0.2s ease;
        z-index: 10;
      }
      
      .popup-close:hover {
        background: rgba(239, 68, 68, 0.2);
        color: #f8fafc;
      }
      
      /* Icon Styles */
      .popup-icon {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
      }
      
      .error-icon {
        background: rgba(239, 68, 68, 0.2);
      }
      
      .success-icon {
        background: rgba(16, 185, 129, 0.2);
      }
      
      .token-icon {
        background: rgba(59, 130, 246, 0.2);
      }
      
      .login-icon {
        background: rgba(139, 92, 246, 0.2);
      }
      
      /* Content Display */
      .content-display {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #475569;
        border-radius: 12px;
        margin: 20px 0;
        position: relative;
        max-height: 300px;
        overflow-y: auto;
        overflow-x: hidden;
      }
      
      .content-text {
        font-family: 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.4;
        color: #e2e8f0;
        white-space: pre-wrap;
        margin: 0;
        padding: 16px;
        word-break: break-all;
        overflow-wrap: anywhere;
      }
      
      /* Custom scrollbar */
      .content-display::-webkit-scrollbar {
        width: 8px;
      }
      
      .content-display::-webkit-scrollbar-track {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 4px;
      }
      
      .content-display::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.8);
        border-radius: 4px;
      }
      
      /* Button Styles */
      .popup-button {
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.2s ease;
        border: none;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
      }
      
      .popup-button-primary {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
      }
      
      .popup-button-primary:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
      }
      
      .popup-button-secondary {
        background: #475569;
        color: #e2e8f0;
      }
      
      .popup-button-secondary:hover {
        background: #64748b;
      }
      
      /* Admin Panel Styles */
      .admin-panel {
        display: none;
      }
      
      .admin-panel.active {
        display: block;
      }
      
      /* Loading Animation */
      .loading {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(255,255,255,.3);
        border-radius: 50%;
        border-top-color: #fff;
        animation: spin 1s ease-in-out infinite;
      }
      
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
      
      /* Loading Overlay */
      .loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 100;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
      }
      
      .loading-overlay.active {
        opacity: 1;
        visibility: visible;
      }
      
      .loading-content {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 16px;
        padding: 24px;
        display: flex;
        align-items: center;
        gap: 16px;
      }
      
      /* Dashboard Styles */
      .dashboard-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(51, 65, 85, 0.8) 100%);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
      }
      
      .dashboard-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
      }
      
      /* Rate Limit Indicator */
      .rate-limit-bar {
        height: 8px;
        background: #334155;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 8px;
      }
      
      .rate-limit-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
        border-radius: 4px;
        transition: width 0.5s ease;
      }
      
      /* Token Expiry Indicator */
      .token-expiry {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
      }
      
      .token-expiry.valid {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
      }
      
      .token-expiry.expired {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
      }
      
      /* Security Badge */
      .security-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
      }
      
      .security-badge.high {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
      }
      
      .security-badge.medium {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
      }
      
      .security-badge.low {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
      }
      
      /* Email Input Enhancement */
      .email-input-container {
        position: relative;
      }
      
      .email-input-icon {
        position: absolute;
        left: 12px;
        top: 50%;
        transform: translateY(-50%);
        color: #64748b;
      }
      
      .email-input {
        padding-left: 40px !important;
      }
      
      /* OTP Status */
      .otp-status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.875rem;
        margin-top: 12px;
      }
      
      .otp-status.sending {
        background: rgba(59, 130, 246, 0.1);
        color: #3b82f6;
      }
      
      .otp-status.sent {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
      }
      
      .otp-status.error {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
      }
      
      /* Step Indicator */
      .step-indicator {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 16px;
      }
      
      .step {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #475569;
        color: #94a3b8;
        font-weight: 600;
        font-size: 14px;
        position: relative;
        z-index: 1;
      }
      
      .step.active {
        background: #3b82f6;
        color: white;
      }
      
      .step.completed {
        background: #10b981;
        color: white;
      }
      
      .step-line {
        flex: 1;
        height: 2px;
        background: #475569;
        margin: 0 8px;
      }
      
      .step-line.completed {
        background: #10b981;
      }
      
      /* Auto Mode Status */
      .auto-status {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 16px;
        margin-top: 16px;
        border-radius: 12px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px dashed rgba(16, 185, 129, 0.3);
      }
      
      .auto-status-icon {
        font-size: 2rem;
        color: #10b981;
        margin-bottom: 8px;
      }
      
      .auto-status-text {
        font-size: 0.875rem;
        color: #10b981;
        font-weight: 500;
      }
      
      /* JWT Decode Status */
      .jwt-status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.875rem;
        margin-top: 12px;
      }
      
      .jwt-status.decoding {
        background: rgba(139, 92, 246, 0.1);
        color: #8b5cf6;
      }
      
      .jwt-status.success {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
      }
      
      .jwt-status.error {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
      }
      
      /* Login Form Styles */
      .login-input {
        width: 100%;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 12px 16px;
        color: #e2e8f0;
        outline: none;
        transition: all 0.2s ease;
        margin-bottom: 16px;
      }
      
      .login-input:focus {
        border-color: #8b5cf6;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
      }
      
      .login-input::placeholder {
        color: #64748b;
      }
      
      /* User Info Styles */
      .user-info {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        background: rgba(139, 92, 246, 0.1);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 8px;
        font-size: 14px;
        color: #a78bfa;
      }
      
      .logout-btn {
        background: none;
        border: none;
        color: #ef4444;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        transition: all 0.2s ease;
      }
      
      .logout-btn:hover {
        background: rgba(239, 68, 68, 0.1);
      }
      
      /* Admin Tabs */
      .admin-tabs {
        display: flex;
        border-bottom: 1px solid #475569;
        margin-bottom: 20px;
      }
      
      .admin-tab {
        padding: 10px 20px;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        transition: all 0.2s ease;
        color: #94a3b8;
        font-weight: 500;
      }
      
      .admin-tab.active {
        color: #a78bfa;
        border-bottom-color: #a78bfa;
      }
      
      .admin-tab:hover {
        color: #a78bfa;
      }
      
      .admin-tab-content {
        display: none;
      }
      
      .admin-tab-content.active {
        display: block;
      }
    </style>
  </head>
  <body class="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 min-h-screen text-slate-100">
    <!-- Loading Overlay -->
    <div id="loadingOverlay" class="loading-overlay">
      <div class="loading-content">
        <div class="loading"></div>
        <span class="text-slate-200">Processing...</span>
      </div>
    </div>
    
    <div class="max-w-6xl mx-auto p-4 sm:p-6">
      <!-- Header -->
      <header class="flex items-center justify-between mb-4 md:mb-8">
        <div class="flex items-center gap-3">
          <h1 class="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight">🚀 -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:- <span class="text-sky-400">Premium</span></h1>
          <div class="security-badge high">
            <i class="fas fa-shield-alt"></i>
            <span>Secured</span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <!-- Admin Login Button (shown when not logged in) -->
          <button id="adminLoginBtn" onclick="showLoginPopup()" class="hidden sm:inline-flex px-3 py-1.5 rounded-md text-xs font-medium bg-violet-600 hover:bg-violet-500 border border-violet-500" {% if admin_logged_in %}style="display: none;"{% endif %}>
            <i class="fas fa-user-shield mr-1"></i> Admin Login
          </button>
          
          <!-- Admin Panel Button (shown when logged in) -->
          <button id="adminPanelBtn" onclick="toggleAdminPanel()" class="hidden sm:inline-flex px-3 py-1.5 rounded-md text-xs font-medium bg-slate-700 hover:bg-slate-600 border border-slate-600" {% if not admin_logged_in %}style="display: none;"{% endif %}>
            <i class="fas fa-cog mr-1"></i> Admin Panel
          </button>
          
          <!-- User Info (shown when logged in) -->
          <div id="userInfo" class="user-info" {% if not admin_logged_in %}style="display: none;"{% endif %}>
            <i class="fas fa-user-circle"></i>
            <span id="username">Admin</span>
            <button class="logout-btn" onclick="logout()" title="Logout">
              <i class="fas fa-sign-out-alt"></i>
            </button>
          </div>
          
          <span class="px-3 py-1 rounded-full text-xs bg-sky-900/60 text-sky-300 border border-sky-700">Web v2.0</span>
        </div>
      </header>
      
      <!-- Admin Panel (Hidden by default) -->
      <div id="adminPanel" class="admin-panel bg-slate-800/70 backdrop-blur rounded-xl border border-slate-700 p-4 sm:p-5 shadow-lg shadow-black/20 mb-6" {% if not admin_logged_in %}style="display: none;"{% endif %}>
        <h2 class="text-lg font-semibold mb-4 text-violet-300 flex items-center">
          <i class="fas fa-user-shield mr-2"></i> Admin Panel
        </h2>
        
        <!-- Admin Tabs -->
        <div class="admin-tabs">
          <div class="admin-tab active" onclick="switchAdminTab('controls')">Admin Controls</div>
          <div class="admin-tab" onclick="switchAdminTab('dashboard')">Dashboard</div>
        </div>
        
        <!-- Admin Controls Tab -->
        <div id="adminControlsTab" class="admin-tab-content active">
          <!-- Stats -->
          <div class="grid grid-cols-3 gap-3 mb-6">
            <div class="bg-slate-900/60 p-3 rounded-lg text-center">
              <div class="text-xs text-slate-400">Total Tokens</div>
              <div class="text-xl font-bold">{{ total }}</div>
            </div>
            <div class="bg-slate-900/60 p-3 rounded-lg text-center">
              <div class="text-xs text-slate-400">Manual</div>
              <div class="text-xl font-bold">{{ manual }}</div>
            </div>
            <div class="bg-slate-900/60 p-3 rounded-lg text-center">
              <div class="text-xs text-slate-400">Auto</div>
              <div class="text-xl font-bold">{{ auto }}</div>
            </div>
          </div>
          
          <!-- Rate Limit Status -->
          <div class="bg-slate-900/60 p-3 rounded-lg mb-4">
            <div class="flex justify-between text-sm mb-1">
              <span class="text-slate-400">Rate Limit Usage</span>
              <span class="text-slate-300">45/200 per day</span>
            </div>
            <div class="rate-limit-bar">
              <div class="rate-limit-fill" style="width: 22.5%"></div>
            </div>
          </div>
          
          <!-- Security Status -->
          <div class="bg-slate-900/60 p-3 rounded-lg mb-4">
            <h3 class="text-sm font-medium text-slate-300 mb-2">Security Status</h3>
            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-400">CSRF Protection</span>
                <span class="text-emerald-400"><i class="fas fa-check-circle"></i> Active</span>
              </div>
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-400">Input Sanitization</span>
                <span class="text-emerald-400"><i class="fas fa-check-circle"></i> Active</span>
              </div>
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-400">Security Headers</span>
                <span class="text-emerald-400"><i class="fas fa-check-circle"></i> Active</span>
              </div>
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-400">Admin Authentication</span>
                <span class="text-emerald-400"><i class="fas fa-check-circle"></i> Active</span>
              </div>
            </div>
          </div>
          
          <!-- Reset Button -->
          <form method="post" action="/admin/reset" class="mb-4">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}" />
            <button type="submit" class="bg-red-600 hover:bg-red-500 text-white py-2 px-4 rounded-md text-sm flex items-center">
              <i class="fas fa-redo mr-2"></i> Reset All Counters
            </button>
          </form>
        </div>
        
        <!-- Dashboard Tab -->
        <div id="dashboardTab" class="admin-tab-content">
          <!-- Dashboard Cards -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div class="dashboard-card">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-slate-300">Active Tokens</h3>
                <i class="fas fa-key text-sky-400"></i>
              </div>
              <div class="text-2xl font-bold text-sky-400">12</div>
              <div class="text-xs text-slate-400 mt-1">Valid for next 24h</div>
            </div>
            
            <div class="dashboard-card">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-slate-300">Total Generated</h3>
                <i class="fas fa-history text-amber-400"></i>
              </div>
              <div class="text-2xl font-bold text-amber-400">47</div>
              <div class="text-xs text-slate-400 mt-1">All time</div>
            </div>
            
            <div class="dashboard-card">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-slate-300">Success Rate</h3>
                <i class="fas fa-percentage text-emerald-400"></i>
              </div>
              <div class="text-2xl font-bold text-emerald-400">96.8%</div>
              <div class="text-xs text-slate-400 mt-1">Last 30 days</div>
            </div>
          </div>
          
          <!-- Recent Tokens -->
          <div class="bg-slate-900/60 rounded-lg p-4">
            <h3 class="text-sm font-medium text-slate-300 mb-3">Recent Tokens</h3>
            <div class="space-y-2">
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-2">
                  <span class="token-expiry valid">Valid</span>
                  <span class="text-slate-300">ey***k3</span>
                </div>
                <span class="text-slate-400 text-xs">2h ago</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-2">
                  <span class="token-expiry valid">Valid</span>
                  <span class="text-slate-300">ey***7m</span>
                </div>
                <span class="text-slate-400 text-xs">5h ago</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-2">
                  <span class="token-expiry expired">Expired</span>
                  <span class="text-slate-300">ey***9q</span>
                </div>
                <span class="text-slate-400 text-xs">1d ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Stats -->
      <div class="grid grid-cols-3 gap-2 sm:gap-3 text-center mb-2">
        <div class="bg-slate-800/70 border border-slate-700 rounded-lg p-2 sm:p-3">
          <div class="text-xs text-slate-400">Tokens (Total)</div>
          <div class="text-lg sm:text-xl font-semibold">{{ total }}</div>
        </div>
        <div class="bg-slate-800/70 border border-slate-700 rounded-lg p-2 sm:p-3">
          <div class="text-xs text-slate-400">Manual</div>
          <div class="text-lg sm:text-xl font-semibold">{{ manual }}</div>
        </div>
        <div class="bg-slate-800/70 border border-slate-700 rounded-lg p-2 sm:p-3">
          <div class="text-xs text-slate-400">Auto</div>
          <div class="text-lg sm:text-xl font-semibold">{{ auto }}</div>
        </div>
      </div>
      <p class="text-xs text-slate-400 mb-4 sm:mb-6">Uptime: {{ (uptime // 3600) }}h {{ ((uptime % 3600) // 60) }}m | Rate Limit: 45/200 per day</p>
      
      <div class="grid md:grid-cols-3 gap-4 sm:gap-6">
        <!-- MANUAL MODE SECTION -->
        <section class="bg-slate-800/70 backdrop-blur rounded-xl border border-slate-700 p-4 sm:p-5 shadow-lg shadow-black/20">
          <h2 class="text-base sm:text-lg font-semibold mb-1 flex items-center">
            <i class="fas fa-hand-pointer mr-2 text-sky-400"></i> Manual Mode
          </h2>
          <p class="text-slate-300 text-sm mb-4">Enter your email and OTP to generate token</p>
          
          <!-- Step Indicator -->
          <div class="step-indicator">
            <div class="step active" id="step1">1</div>
            <div class="step-line" id="line1"></div>
            <div class="step" id="step2">2</div>
          </div>
          
          <!-- Step 1: Email Input -->
          <div id="step1Content">
            <div class="email-input-container mb-4">
              <i class="fas fa-envelope email-input-icon"></i>
              <input 
                id="manualEmail" 
                class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600 email-input" 
                type="email" 
                placeholder="you@example.com" 
              />
            </div>
            
            <button id="sendOtpBtn" class="w-full bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium flex items-center justify-center">
              <i class="fas fa-paper-plane mr-2"></i> Send OTP
            </button>
          </div>
          
          <!-- Step 2: OTP Input (Hidden by default) -->
          <div id="step2Content" style="display: none;">
            <div class="mb-4">
              <label class="block text-sm mb-1">Enter OTP</label>
              <input 
                id="manualOtp" 
                class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600 text-center text-lg tracking-widest" 
                type="text" 
                minlength="4" 
                maxlength="4" 
                pattern="\\d{4}" 
                placeholder="0000" 
              />
            </div>
            
            <button id="generateTokenBtn" class="w-full bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium flex items-center justify-center">
              <i class="fas fa-key mr-2"></i> Generate Token
            </button>
            
            <button id="backToEmailBtn" class="w-full mt-2 bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium flex items-center justify-center">
              <i class="fas fa-arrow-left mr-2"></i> Back to Email
            </button>
          </div>
          
          <!-- OTP Status -->
          <div id="otpStatus" class="otp-status sending" style="display: none;">
            <i class="fas fa-spinner fa-spin"></i>
            <span>Sending OTP...</span>
          </div>
          
          <!-- Info Box -->
          <div class="mt-4 p-3 bg-slate-900/40 rounded-lg border border-slate-700">
            <div class="flex items-start">
              <i class="fas fa-info-circle text-sky-400 mt-0.5 mr-2 flex-shrink-0"></i>
              <p class="text-xs text-slate-400">Enter your email to receive OTP. Check your inbox and enter the OTP to generate token.</p>
            </div>
          </div>
        </section>
        
        <!-- AUTO MODE SECTION -->
        <section class="bg-slate-800/70 backdrop-blur rounded-xl border border-slate-700 p-4 sm:p-5 shadow-lg shadow-black/20">
          <div class="text-center mb-4">
            <div class="inline-flex items-center justify-center w-12 h-12 bg-emerald-500/20 rounded-full mb-3">
              <i class="fas fa-bolt text-emerald-400 text-xl"></i>
            </div>
            <h2 class="text-base sm:text-lg font-semibold mb-1">Auto Mode</h2>
            <p class="text-slate-300 text-sm">Generate token instantly with one click</p>
          </div>
          
          <form method="post" action="{{ url_for('auto_web') }}" class="space-y-4">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}" />
            <button type="submit" id="autoBtn" class="w-full bg-emerald-600 hover:bg-emerald-500 transition-all duration-300 rounded px-4 py-3 font-medium flex items-center justify-center group">
              <i class="fas fa-magic mr-2 group-hover:rotate-12 transition-transform"></i>
              Generate Token Automatically
            </button>
          </form>
          
          <!-- Auto Mode Status (Hidden by default) -->
          <div id="autoStatus" class="auto-status" style="display: none;">
            <i class="fas fa-check-circle auto-status-icon"></i>
            <div class="auto-status-text">Token generated successfully!</div>
          </div>
          
          <div class="mt-4 p-3 bg-slate-900/40 rounded-lg border border-slate-700">
            <div class="flex items-start">
              <i class="fas fa-exclamation-triangle text-amber-400 mt-0.5 mr-2 flex-shrink-0"></i>
              <p class="text-xs text-slate-400">This will take 30-60 seconds. All processing happens in background with rate limiting.</p>
            </div>
          </div>
        </section>
        
        <!-- JWT DECODE SECTION -->
        <section class="bg-slate-800/70 backdrop-blur rounded-xl border border-slate-700 p-4 sm:p-5 shadow-lg shadow-black/20">
          <h2 class="text-base sm:text-lg font-semibold mb-1 flex items-center">
            <i class="fas fa-code mr-2 text-violet-400"></i> Decode JWT
          </h2>
          <p class="text-slate-300 text-sm mb-4">Paste any JWT; we decode header & payload.</p>
          
          <!-- JWT Form -->
          <form id="jwtForm" method="post" action="{{ url_for('jwt_decode_public') }}">
            <textarea id="jwtInput" name="jwt" class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2" rows="5" placeholder="eyJhbGciOi..."></textarea>
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}" />
            <button id="jwtDecodeBtn" type="submit" class="w-full bg-violet-600 hover:bg-violet-500 transition-colors rounded px-4 py-2 font-medium flex items-center justify-center mt-3">
              <i class="fas fa-unlock-alt mr-2"></i> Decode
            </button>
          </form>
          
          <!-- JWT Status (Hidden by default) -->
          <div id="jwtStatus" class="jwt-status decoding" style="display: none;">
            <i class="fas fa-spinner fa-spin"></i>
            <span>Decoding JWT...</span>
          </div>
          
          <div class="mt-4 p-3 bg-slate-900/40 rounded-lg border border-slate-700">
            <div class="flex items-start">
              <i class="fas fa-info-circle text-violet-400 mt-0.5 mr-2 flex-shrink-0"></i>
              <p class="text-xs text-slate-400">JWT will be decoded and displayed in a popup. You can copy the decoded content from there.</p>
            </div>
          </div>
        </section>
      </div>
      
      <section class="mt-6 sm:mt-8">
        <h3 class="text-sm font-semibold mb-2 text-slate-200 flex items-center">
          <i class="fas fa-history mr-2"></i> Recent activity
        </h3>
        <div class="bg-slate-800/70 border border-slate-700 rounded-lg p-4 text-sm">
          {% if recent and recent|length > 0 %}
            <ul class="space-y-1">
              {% for e in recent %}
                <li class="flex items-center justify-between">
                  <span class="text-slate-300">{{ e.mode|capitalize }} • {{ e.email|mask_email }}</span>
                  <span class="text-slate-400 text-xs">{{ e.ts }}</span>
                </li>
              {% endfor %}
            </ul>
          {% else %}
            <p class="text-slate-400">No recent events yet.</p>
          {% endif %}
        </div>
      </section>
      
      <footer class="mt-6 sm:mt-8 text-center text-xs text-slate-400">
        <p>© -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:- Premium v2.0 | Secured with SSL & CSRF Protection</p>
        <p class="mt-1">Rate Limited: 200/day | Token Expiry: 24h | Logs: Enabled</p>
      </footer>
    </div>
    
    <!-- ERROR POPUP -->
    <div id="errorPopup" class="popup-overlay">
      <div class="popup-content">
        <button class="popup-close" onclick="closePopup('errorPopup')">&times;</button>
        
        <div class="popup-icon error-icon">
          <i class="fas fa-exclamation-triangle text-red-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-red-300 mb-3">Error</h3>
        <p class="text-sm text-center text-slate-300 mb-6" id="errorMessage">Invalid email address</p>
        
        <div class="flex justify-center">
          <button onclick="closePopup('errorPopup')" class="popup-button popup-button-primary">
            <i class="fas fa-check mr-2"></i> OK
          </button>
        </div>
      </div>
    </div>
    
    <!-- SUCCESS POPUP -->
    <div id="successPopup" class="popup-overlay">
      <div class="popup-content">
        <button class="popup-close" onclick="closePopup('successPopup')">&times;</button>
        
        <div class="popup-icon success-icon">
          <i class="fas fa-check-circle text-emerald-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-emerald-300 mb-3">Success</h3>
        <p class="text-sm text-center text-slate-300 mb-6" id="successMessage">OTP sent to a***n@gmail.com</p>
        
        <div class="flex justify-center">
          <button onclick="closePopup('successPopup')" class="popup-button popup-button-primary">
            <i class="fas fa-check mr-2"></i> OK
          </button>
        </div>
      </div>
    </div>
    
    <!-- TOKEN POPUP -->
    <div id="tokenPopup" class="popup-overlay">
      <div class="popup-content">
        <button class="popup-close" onclick="closePopup('tokenPopup')">&times;</button>
        
        <div class="popup-icon token-icon">
          <i class="fas fa-key text-blue-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-blue-300 mb-3">🎉 Token Generated!</h3>
        
        <div class="content-display">
          <pre class="content-text" id="tokenText">eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c</pre>
        </div>
        
        <div class="flex justify-center gap-3">
          <button onclick="copyToken()" class="popup-button popup-button-primary">
            <i class="fas fa-copy mr-2"></i> Copy Token
          </button>
          <button onclick="closePopup('tokenPopup')" class="popup-button popup-button-secondary">
            <i class="fas fa-times mr-2"></i> Close
          </button>
        </div>
      </div>
    </div>
    
    <!-- LOGIN POPUP -->
    <div id="loginPopup" class="popup-overlay">
      <div class="popup-content">
        <button class="popup-close" onclick="closePopup('loginPopup')">&times;</button>
        
        <div class="popup-icon login-icon">
          <i class="fas fa-user-shield text-violet-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-violet-300 mb-3">Admin Login</h3>
        
        <form id="loginForm" method="post" action="{{ url_for('admin_login') }}">
          <input 
            type="text" 
            id="loginUsername" 
            name="username"
            class="login-input" 
            placeholder="Username" 
            required 
          />
          <input 
            type="password" 
            id="loginPassword" 
            name="password"
            class="login-input" 
            placeholder="Password" 
            required 
          />
          <input type="hidden" name="csrf_token" value="{{ csrf_token }}" />
          <button type="submit" class="w-full bg-violet-600 hover:bg-violet-500 transition-colors rounded px-4 py-2 font-medium">
            <i class="fas fa-sign-in-alt mr-2"></i> Login
          </button>
        </form>
        
        <div class="mt-4 p-3 bg-slate-900/40 rounded-lg border border-slate-700">
          <div class="flex items-start">
            <i class="fas fa-info-circle text-violet-400 mt-0.5 mr-2 flex-shrink-0"></i>
            <p class="text-xs text-slate-400">Default credentials: admin / admin123</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- JWT RESULT POPUP -->
    <div id="jwtResultPopup" class="popup-overlay">
      <div class="popup-content">
        <button class="popup-close" onclick="closePopup('jwtResultPopup')">&times;</button>
        
        <div class="popup-icon" style="background: rgba(139, 92, 246, 0.2);">
          <i class="fas fa-file-code text-violet-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-violet-300 mb-3">JWT Decoded</h3>
        
        <div id="jwtResultContent" class="content-display">
          <pre class="content-text" id="jwtResultText">Loading...</pre>
        </div>
        
        <div class="flex justify-center gap-3 mt-4">
          <button onclick="copyDecodedJWT()" class="popup-button popup-button-primary">
            <i class="fas fa-copy mr-2"></i> Copy Decoded JWT
          </button>
          <button onclick="closePopup('jwtResultPopup')" class="popup-button popup-button-secondary">
            <i class="fas fa-times mr-2"></i> Close
          </button>
        </div>
      </div>
    </div>
    
    <script>
      // Global state
      let isLoggedIn = {{ 'true' if admin_logged_in else 'false' }};
      let privateMode = {{ 'true' if PRIVATE_MODE else 'false' }};
      let accessKey = "{{ access_key }}";
      
      // Show popup on page load if needed
      document.addEventListener('DOMContentLoaded', function() {
        // Setup manual mode
        setupManualMode();
        
        // Setup JWT decode
        setupJWTDecode();
      });
      
      // Setup manual mode with proper steps
      function setupManualMode() {
        const emailInput = document.getElementById('manualEmail');
        const sendOtpBtn = document.getElementById('sendOtpBtn');
        const otpInput = document.getElementById('manualOtp');
        const generateTokenBtn = document.getElementById('generateTokenBtn');
        const backToEmailBtn = document.getElementById('backToEmailBtn');
        const otpStatus = document.getElementById('otpStatus');
        
        const step1Content = document.getElementById('step1Content');
        const step2Content = document.getElementById('step2Content');
        const step1 = document.getElementById('step1');
        const step2 = document.getElementById('step2');
        const line1 = document.getElementById('line1');
        
        // Send OTP button click
        sendOtpBtn.addEventListener('click', function() {
          const email = emailInput.value.trim();
          
          if (!email) {
            showPopup('error', { message: "Please enter your email address" });
            return;
          }
          
          if (!validateEmail(email)) {
            showPopup('error', { message: "Please enter a valid email address" });
            return;
          }
          
          // Show sending status
          otpStatus.className = 'otp-status sending';
          otpStatus.style.display = 'flex';
          otpStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Sending OTP...</span>';
          sendOtpBtn.disabled = true;
          sendOtpBtn.classList.add('opacity-50', 'cursor-not-allowed');
          
          // Send OTP to backend
          fetch('/send-otp', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ email: email })
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              // Show success status
              otpStatus.className = 'otp-status sent';
              otpStatus.innerHTML = '<i class="fas fa-check-circle"></i><span>OTP sent successfully!</span>';
              
              // Move to step 2
              step1Content.style.display = 'none';
              step2Content.style.display = 'block';
              step1.classList.remove('active');
              step1.classList.add('completed');
              step2.classList.add('active');
              line1.classList.add('completed');
              
              // Focus on OTP input
              otpInput.focus();
              
              // Show success popup
              showPopup('success', { 
                message: `OTP sent to ${maskEmail(email)}` 
              });
              
              // Store session data for verification
              sessionStorage.setItem('sessionId', data.session_id);
              sessionStorage.setItem('deviceId', data.device_id);
              sessionStorage.setItem('orgId', data.org_id);
              sessionStorage.setItem('orgCode', data.org_code);
            } else {
              // Show error status
              otpStatus.className = 'otp-status error';
              otpStatus.innerHTML = `<i class="fas fa-exclamation-circle"></i><span>${data.error}</span>`;
              
              // Show error popup
              showPopup('error', { message: data.error });
              
              // Reset button
              sendOtpBtn.disabled = false;
              sendOtpBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
          })
          .catch(error => {
            console.error('Error:', error);
            otpStatus.className = 'otp-status error';
            otpStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i><span>Network error. Please try again.</span>';
            
            // Reset button
            sendOtpBtn.disabled = false;
            sendOtpBtn.classList.remove('opacity-50', 'cursor-not-allowed');
          });
        });
        
        // Generate token button click
        generateTokenBtn.addEventListener('click', function() {
          const otp = otpInput.value.trim();
          
          if (!otp) {
            showPopup('error', { message: "Please enter the OTP" });
            return;
          }
          
          if (!/^\\d{4}$/.test(otp)) {
            showPopup('error', { message: "OTP must be 4 digits" });
            return;
          }
          
          // Show loading overlay
          document.getElementById('loadingOverlay').classList.add('active');
          
          // Get session data
          const sessionId = sessionStorage.getItem('sessionId');
          const deviceId = sessionStorage.getItem('deviceId');
          const orgId = sessionStorage.getItem('orgId');
          const orgCode = sessionStorage.getItem('orgCode');
          const email = emailInput.value.trim();
          
          // Verify OTP with backend
          fetch('/verify-otp', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ 
              email: email,
              otp: otp,
              session_id: sessionId,
              device_id: deviceId,
              org_id: orgId,
              org_code: orgCode
            })
          })
          .then(response => response.json())
          .then(data => {
            document.getElementById('loadingOverlay').classList.remove('active');
            
            if (data.success) {
              // Show token popup
              showPopup('token', { token: data.token });
              
              // Reset form
              resetManualForm();
            } else {
              // Show error popup
              showPopup('error', { message: data.error });
            }
          })
          .catch(error => {
            console.error('Error:', error);
            document.getElementById('loadingOverlay').classList.remove('active');
            showPopup('error', { message: "Network error. Please try again." });
          });
        });
        
        // Back to email button click
        backToEmailBtn.addEventListener('click', function() {
          resetManualForm();
        });
        
        // Enter key on email input
        emailInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            sendOtpBtn.click();
          }
        });
        
        // Enter key on OTP input
        otpInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            generateTokenBtn.click();
          }
        });
        
        function resetManualForm() {
          // Reset form
          emailInput.value = '';
          otpInput.value = '';
          
          // Reset UI
          step1Content.style.display = 'block';
          step2Content.style.display = 'none';
          step1.classList.add('active');
          step1.classList.remove('completed');
          step2.classList.remove('active');
          line1.classList.remove('completed');
          
          // Reset buttons
          sendOtpBtn.disabled = false;
          sendOtpBtn.classList.remove('opacity-50', 'cursor-not-allowed');
          
          // Hide status
          otpStatus.style.display = 'none';
          
          // Focus on email
          emailInput.focus();
        }
      }
      
      // Setup JWT decode
      function setupJWTDecode() {
        const jwtForm = document.getElementById('jwtForm');
        
        // Handle form submission
        jwtForm.addEventListener('submit', function(e) {
          e.preventDefault();
          
          const jwtInput = document.getElementById('jwtInput');
          const jwtToken = jwtInput.value.trim();
          
          if (!jwtToken) {
            showPopup('error', { message: "Please enter a JWT token" });
            return;
          }
          
          // Show loading overlay
          document.getElementById('loadingOverlay').classList.add('active');
          
          // Submit form normally (not AJAX for simplicity)
          jwtForm.submit();
        });
      }
      
      // Auto mode loading state
      document.getElementById('autoBtn')?.addEventListener('click', function(e) {
        // Form will submit normally, so we don't need to do anything here
        // The loading overlay will be shown by the backend response
      });
      
      // Email validation
      function validateEmail(email) {
        const re = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
        return re.test(email);
      }
      
      // Email masking
      function maskEmail(email) {
        const [localPart, domain] = email.split('@');
        const maskedLocal = localPart[0] + '***' + localPart[localPart.length - 1];
        return maskedLocal + '@' + domain;
      }
      
      // Show login popup
      function showLoginPopup() {
        document.getElementById('loginPopup').classList.add('active');
        document.getElementById('loginUsername').focus();
      }
      
      // Logout
      function logout() {
        // Redirect to logout endpoint
        window.location.href = '/admin/logout';
      }
      
      // Toggle admin panel
      function toggleAdminPanel() {
        const panel = document.getElementById('adminPanel');
        panel.classList.toggle('active');
      }
      
      // Switch admin tab
      function switchAdminTab(tabName) {
        // Remove active class from all tabs and contents
        document.querySelectorAll('.admin-tab').forEach(tab => {
          tab.classList.remove('active');
        });
        document.querySelectorAll('.admin-tab-content').forEach(content => {
          content.classList.remove('active');
        });
        
        // Add active class to selected tab and content
        if (tabName === 'controls') {
          document.querySelector('.admin-tab:nth-child(1)').classList.add('active');
          document.getElementById('adminControlsTab').classList.add('active');
        } else if (tabName === 'dashboard') {
          document.querySelector('.admin-tab:nth-child(2)').classList.add('active');
          document.getElementById('dashboardTab').classList.add('active');
        }
      }
      
      // Show popup function
      function showPopup(type, data = {}) {
        const popup = document.getElementById(type + 'Popup');
        
        // Set data based on popup type
        if (type === 'error' || type === 'success') {
          const messageElement = document.getElementById(type + 'Message');
          if (messageElement && data.message) {
            messageElement.textContent = data.message;
          }
        } else if (type === 'token') {
          const tokenElement = document.getElementById('tokenText');
          if (tokenElement && data.token) {
            tokenElement.textContent = data.token;
          }
        }
        
        popup.classList.add('active');
      }
      
      // Close popup function
      function closePopup(popupId) {
        const popup = document.getElementById(popupId);
        popup.classList.remove('active');
      }
      
      // Copy token function
      function copyToken() {
        const tokenText = document.getElementById('tokenText').textContent;
        navigator.clipboard.writeText(tokenText).then(() => {
          const button = event.target.closest('button');
          const originalHTML = button.innerHTML;
          button.innerHTML = `
            <i class="fas fa-check mr-2"></i> Copied!
          `;
          button.classList.add('bg-emerald-600');
          
          setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('bg-emerald-600');
          }, 2000);
        });
      }
      
      // Copy decoded JWT function
      function copyDecodedJWT() {
        const jwtText = document.getElementById('jwtResultText').textContent;
        navigator.clipboard.writeText(jwtText).then(() => {
          const button = event.target.closest('button');
          const originalHTML = button.innerHTML;
          button.innerHTML = `
            <i class="fas fa-check mr-2"></i> Copied!
          `;
          button.classList.add('bg-emerald-600');
          
          setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('bg-emerald-600');
          }, 2000);
        });
      }
      
      // Close popup when clicking outside
      document.addEventListener('click', function(event) {
        if (event.target.classList.contains('popup-overlay')) {
          event.target.classList.remove('active');
        }
      });
    </script>
  </body>
</html>
        """,
        total=TOKEN_COUNT_TOTAL,
        manual=TOKEN_COUNT_MANUAL,
        auto=TOKEN_COUNT_AUTO,
        uptime=int(time.time() - start_time),
        recent=list(RECENT_EVENTS)[-10:][::-1],
        admin_logged_in=admin_logged_in,
        csrf_token=csrf_token,
        access_key=request.cookies.get('access') or request.args.get("access") or request.headers.get("x-access-key"),
    )

@app.post("/access")
def access_gate():
    if not PRIVATE_MODE:
        return redirect(url_for('home'))
    key = (request.form.get('access') or '').strip()
    if not key:
        return redirect(url_for('home'))
    ok = False
    if ACCESS_KEY and key == ACCESS_KEY:
        ok = True
    if ACCESS_KEYS and key in ACCESS_KEYS:
        ok = True
    if not ok:
        return redirect(url_for('home'))
    resp = make_response(redirect(url_for('home')))
    # Set short-lived cookie (e.g., 1 day)
    resp.set_cookie('access', key, max_age=86400, secure=False, httponly=True, samesite='Lax')
    return resp

@app.post("/send-otp")
def send_otp_web():
    if not _gate_ok(request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": "Forbidden"}), 403
        else:
            return ("Forbidden", 403)
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax:
        data = request.get_json()
        email = (data.get("email") or "").strip()
    else:
        email = (request.form.get("email") or "").strip()
    
    # Always random org selection for privacy/consistency
    choice = _random.choice(ORG_CONFIGS)
    org_code, org_id = choice["org_code"], choice["org_id"]

    if not email or "@" not in email or "." not in email:
        if is_ajax:
            return jsonify({"success": False, "error": "Invalid email"})
        else:
            return render_template_string("""
                <p>❌ Invalid email. <a href='{{ url_for("home") }}'>Back</a></p>
            """)

    otp_result = send_otp_email(email, org_code, org_id)
    if not otp_result.get("success"):
        if is_ajax:
            return jsonify({"success": False, "error": otp_result.get("error")})
        else:
            return render_template_string(
                """
                <p>❌ OTP send failed: {{ err }}</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
                """,
                err=otp_result.get("error"),
            )

    session_id = otp_result.get("session_id")
    device_id = otp_result.get("device_id")
    org_code = otp_result.get("org_code", org_code)
    
    if is_ajax:
        return jsonify({
            "success": True,
            "session_id": session_id,
            "device_id": device_id,
            "org_id": org_id,
            "org_code": org_code
        })
    else:
        # Original HTML response for non-AJAX requests
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Verify OTP — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-md bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-1">Verify OTP</h2>
      <p class="text-slate-300 text-sm mb-4">Enter the 4‑digit code sent to <span class="text-sky-300">{{ email|mask_email }}</span>.</p>
      <form method="post" action="{{ url_for('verify_otp_web') }}" class="space-y-4">
        <input type="hidden" name="email" value="{{ email }}" />
        <input type="hidden" name="org_id" value="{{ org_id }}" />
        <input type="hidden" name="device_id" value="{{ device_id }}" />
        <input type="hidden" name="org_code" value="{{ org_code }}" />
        <div>
          <label class="block text-sm mb-1">4-digit OTP</label>
          <input class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600" type="text" name="otp" minlength="4" maxlength="4" pattern="\\d{4}" required />
        </div>
        <button class="w-full bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium">Verify</button>
      </form>
      <div class="flex items-center justify-between mt-4">
        <a class="text-xs underline hover:text-sky-300 text-slate-400" href='{{ url_for("home") }}'>Start over</a>
        <form method="post" action="{{ url_for('resend_otp') }}">
          <input type="hidden" name="email" value="{{ email }}" />
          <input type="hidden" name="org_id" value="{{ org_id }}" />
          <input type="hidden" name="org_code" value="{{ org_code }}" />
          <button id="resendBtn" class="text-xs text-slate-300 underline disabled:opacity-50" disabled>Resend in 30s</button>
        </form>
      </div>
      <script>
        let s = 30; const btn = document.getElementById('resendBtn');
        const timer = setInterval(()=>{ s--; if(s<=0){ btn.disabled=false; btn.textContent='Resend OTP'; clearInterval(timer); } else { btn.textContent=`Resend in ${s}s`; } }, 1000);
      </script>
    </div>
  </body>
</html>
            """,
            email=mask_email_address(email),
            session_id=session_id,
            org_id=org_id,
            device_id=device_id,
            org_code=org_code,
        )

@app.post("/verify-otp")
def verify_otp_web():
    if not _gate_ok(request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": "Forbidden"}), 403
        else:
            return ("Forbidden", 403)
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax:
        data = request.get_json()
        email = (data.get("email") or "").strip()
        otp = (data.get("otp") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        org_id = (data.get("org_id") or "").strip()
        device_id = (data.get("device_id") or "").strip()
        org_code = (data.get("org_code") or "").strip()
    else:
        email = (request.form.get("email") or "").strip()
        otp = (request.form.get("otp") or "").strip()
        session_id = (request.form.get("session_id") or "").strip()
        org_id = (request.form.get("org_id") or "").strip()
        device_id = (request.form.get("device_id") or "").strip()
        org_code = (request.form.get("org_code") or "").strip()
    
    if not otp or not otp.isdigit() or len(otp) != 4:
        if is_ajax:
            return jsonify({"success": False, "error": "Invalid OTP"})
        else:
            return render_template_string("""
                <p>❌ Invalid OTP. <a href='{{ url_for("home") }}'>Home</a></p>
            """)
    
    result = verify_otp_email(email, otp, session_id, org_id, device_id, org_code)
    if not result.get("success"):
        if is_ajax:
            return jsonify({"success": False, "error": result.get("error")})
        else:
            return render_template_string(
                """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Retry — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-md bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <p class="text-rose-400 text-sm mb-3">❌ {{ err }}</p>
      <form method="post" action="{{ url_for('verify_otp_web') }}" class="space-y-3">
        <input type="hidden" name="email" value="{{ email }}" />
        <input type="hidden" name="session_id" value="{{ session_id }}" />
        <input type="hidden" name="org_id" value="{{ org_id }}" />
        <input type="hidden" name="device_id" value="{{ device_id }}" />
        <input type="hidden" name="org_code" value="{{ org_code }}" />
        <div>
          <label class="block text-sm mb-1">4-digit OTP</label>
          <input class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600" type="text" name="otp" minlength="4" maxlength="4" pattern="\\d{4}" required />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <button class="bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium" type="submit">Retry Verify</button>
          <a class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium text-center" href='{{ url_for("home") }}'>Home</a>
        </div>
      </form>
    </div>
  </body>
</html>
                """,
                err=result.get("error"), email=email, session_id=session_id, org_id=org_id, device_id=device_id, org_code=org_code,
            )
    
    token = result.get("token")
    _inc_token_count("manual")
    try:
        RECENT_EVENTS.append({"mode": "manual", "email": email, "ts": int(time.time())})
    except Exception:
        pass
    
    if is_ajax:
        return jsonify({"success": True, "token": token})
    else:
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Token — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-2xl bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-2">✅ Token Generated</h2>
      <div class="bg-slate-900/60 border border-slate-700 rounded p-4">
        <pre id="token" class="whitespace-pre-wrap break-words blur-sm" data-revealed="0">{{ token }}</pre>
      </div>
      <div class="flex gap-3 mt-4">
        <button id="revealBtn" class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium" onclick="const t=document.getElementById('token'); if(t.dataset.revealed==='0'){t.classList.remove('blur-sm'); t.dataset.revealed='1'; this.textContent='Hide';} else {t.classList.add('blur-sm'); t.dataset.revealed='0'; this.textContent='Reveal';} return false;">Reveal</button>
        <button class="bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium" onclick="navigator.clipboard.writeText(document.getElementById('token').innerText).then(()=>{this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy',1200);})">Copy</button>
        <a class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium" href='{{ url_for("home") }}'>Generate another</a>
      </div>
    </div>
  </body>
</html>
            """,
            token=token,
        )

@app.post("/resend-otp")
def resend_otp():
    if not _gate_ok(request):
        return ("Forbidden", 403)
    email = (request.form.get("email") or "").strip()
    org_id = (request.form.get("org_id") or "").strip()
    org_code = (request.form.get("org_code") or "").strip()
    if not email or not org_id:
        return redirect(url_for('home'))
    otp_result = send_otp_email(email, org_code, org_id)
    if not otp_result.get("success"):
        return render_template_string(
            """
            <p>❌ OTP send failed: {{ err }}</p>
            <p><a href='{{ url_for("home") }}'>Home</a></p>
            """,
            err=otp_result.get("error"),
        )
    # Redirect back to verify page with new session
    return render_template_string(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Verify OTP — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-md bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-1">Verify OTP</h2>
      <p class="text-slate-300 text-sm mb-4">New OTP sent to <span class="text-sky-300">{{ email|mask_email }}</span>. Enter the 4‑digit code.</p>
      <form method="post" action="{{ url_for('verify_otp_web') }}" class="space-y-4">
        <input type="hidden" name="email" value="{{ email }}" />
        <input type="hidden" name="session_id" value="{{ session_id }}" />
        <input type="hidden" name="org_id" value="{{ org_id }}" />
        <input type="hidden" name="device_id" value="{{ device_id }}" />
        <input type="hidden" name="org_code" value="{{ org_code }}" />
        <div>
          <label class="block text-sm mb-1">4-digit OTP</label>
          <input class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2 outline-none focus:ring-2 focus:ring-sky-600" type="text" name="otp" minlength="4" maxlength="4" pattern="\\d{4}" required />
        </div>
        <button class="w-full bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium">Verify</button>
      </form>
      <div class="flex items-center justify-between mt-4">
        <a class="text-xs underline hover:text-sky-300 text-slate-400" href='{{ url_for("home") }}'>Start over</a>
        <form method="post" action="{{ url_for('resend_otp') }}">
          <input type="hidden" name="email" value="{{ email }}" />
          <input type="hidden" name="org_id" value="{{ org_id }}" />
          <input type="hidden" name="org_code" value="{{ org_code }}" />
          <button id="resendBtn" class="text-xs text-slate-300 underline disabled:opacity-50" disabled>Resend in 30s</button>
        </form>
      </div>
      <script>
        let s = 30; const btn = document.getElementById('resendBtn');
        const timer = setInterval(()=>{ s--; if(s<=0){ btn.disabled=false; btn.textContent='Resend OTP'; clearInterval(timer); } else { btn.textContent=`Resend in ${s}s`; } }, 1000);
      </script>
    </div>
  </body>
</html>
        """,
        email=email,
        session_id=otp_result.get("session_id"),
        org_id=otp_result.get("org_id", org_id),
        device_id=otp_result.get("device_id"),
        org_code=otp_result.get("org_code", org_code),
    )

@app.post("/auto")
def auto_web():
    if not _gate_ok(request):
        return ("Forbidden", 403)
    
    gmail = (request.form.get("gmail") or "").strip()
    if not gmail or "@" not in gmail:
        return render_template_string("""
            <p>❌ Invalid Gmail. <a href='{{ url_for("home") }}'>Back</a></p>
        """)
    
    try:
        if not USER_EMAIL_ADDRESS or not USER_EMAIL_APP_PASSWORD:
            return render_template_string("""
                <p>❌ Server missing EMAIL_ADDRESS or EMAIL_APP_PASSWORD. Configure env vars.</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
            """)
        
        # Show loading page
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Processing — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
      .spinner {
        animation: spin 2s linear infinite;
      }
    </style>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 flex items-center justify-center p-6">
    <div class="w-full max-w-md bg-slate-800/70 border border-slate-700 rounded-xl p-8 shadow-xl text-center">
      <div class="spinner text-5xl text-emerald-400 mb-6">
        <i class="fas fa-cog"></i>
      </div>
      <h2 class="text-xl font-semibold mb-2">Processing Auto Mode</h2>
      <p class="text-slate-300 mb-4">Please wait while we generate your token...</p>
      <p class="text-slate-400 text-sm">This usually takes 30-60 seconds.</p>
      
      <form id="autoForm" method="post" action="{{ url_for('auto_process') }}">
        <input type="hidden" name="gmail" value="{{ gmail }}" />
      </form>
      
      <script>
        document.addEventListener('DOMContentLoaded', function() {
          document.getElementById('autoForm').submit();
        });
      </script>
    </div>
  </body>
</html>
            """,
            gmail=gmail
        )
    except Exception as e:
        return render_template_string(
            """
            <p>❌ Auto error: {{ err }}</p>
            <p><a href='{{ url_for("home") }}'>Back</a></p>
            """,
            err=str(e),
        )

@app.post("/auto/process")
def auto_process():
    if not _gate_ok(request):
        return ("Forbidden", 403)
    
    gmail = (request.form.get("gmail") or "").strip()
    if not gmail or "@" not in gmail:
        return render_template_string("""
            <p>❌ Invalid Gmail. <a href='{{ url_for("home") }}'>Back</a></p>
        """)
    
    try:
        if not USER_EMAIL_ADDRESS or not USER_EMAIL_APP_PASSWORD:
            return render_template_string("""
                <p>❌ Server missing EMAIL_ADDRESS or EMAIL_APP_PASSWORD. Configure env vars.</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
            """)
        
        inbox = GmailAliasClient(USER_EMAIL_ADDRESS, USER_EMAIL_APP_PASSWORD)
        alias = inbox.generate_alias()
        
        # Always random org selection
        choice = _random.choice(ORG_CONFIGS)
        org_code, org_id = choice["org_code"], choice["org_id"]

        otp_result = send_otp_email(alias, org_code, org_id)
        if not otp_result.get("success"):
            return render_template_string(
                """
                <p>❌ OTP request failed: {{ err }}</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
                """,
                err=otp_result.get("error"),
            )
        
        session_id = otp_result["session_id"]
        device_id = otp_result["device_id"]

        otp_code = None
        deadline = time.time() + 60
        last_seen = set()
        while time.time() < deadline and not otp_code:
            try:
                msgs = inbox.list_messages(alias) or []
                for m in msgs:
                    mid = m.get("id")
                    if not mid or mid in last_seen:
                        continue
                    last_seen.add(mid)
                    detail = inbox.read_message(mid)
                    body = (detail.get("text", "") or "")
                    match = re.search(r"\b(\d{4})\b", body)
                    if match:
                        otp_code = match.group(1)
                        break
            except Exception:
                pass
            time.sleep(1)

        if not otp_code:
            return render_template_string(
                """
                <p>OTP not received for alias {{ alias }}. Try manual mode.</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
                """,
                alias=mask_email_address(alias),
            )

        result = verify_otp_email(alias, otp_code, session_id, org_id, device_id, org_code)
        if not result.get("success"):
            return render_template_string(
                """
                <p>❌ Auto failed: {{ err }}</p>
                <p><a href='{{ url_for("home") }}'>Back</a></p>
                """,
                err=result.get("error"),
            )
        
        token = result.get("token")
        _inc_token_count("auto")
        try:
            RECENT_EVENTS.append({"mode": "auto", "email": mask_email_address(alias), "ts": int(time.time())})
        except Exception:
            pass
        
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Token — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-2xl bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-2">✅ Token Generated (Auto)</h2>
      <div class="bg-slate-900/60 border border-slate-700 rounded p-4">
        <pre id="token" class="whitespace-pre-wrap break-words blur-sm" data-revealed="0">{{ token }}</pre>
      </div>
      <div class="flex gap-3 mt-4">
        <button id="revealBtn" class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium" onclick="const t=document.getElementById('token'); if(t.dataset.revealed==='0'){t.classList.remove('blur-sm'); t.dataset.revealed='1'; this.textContent='Hide';} else {t.classList.add('blur-sm'); t.dataset.revealed='0'; this.textContent='Reveal';} return false;">Reveal</button>
        <button class="bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium" onclick="navigator.clipboard.writeText(document.getElementById('token').innerText).then(()=>{this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy',1200);})">Copy</button>
        <a class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium" href='{{ url_for("home") }}'>Generate another</a>
      </div>
    </div>
  </body>
</html>
            """,
            token=token,
        )
    except Exception as e:
        return render_template_string(
            """
            <p>❌ Auto error: {{ err }}</p>
            <p><a href='{{ url_for("home") }}'>Back</a></p>
            """,
            err=str(e),
        )

@app.post("/jwt-decode")
def jwt_decode_public():
    token = (request.form.get('jwt') or '').strip()
    if not token or token.count('.') != 2:
        return render_template_string("""
            <p>❌ Invalid JWT format. <a href='{{ url_for("home") }}'>Home</a></p>
        """)
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
        def b64url_decode(data):
            data += '=' * (-len(data) % 4)
            return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8', errors='ignore')
        header_json = b64url_decode(header_b64)
        payload_json = b64url_decode(payload_b64)
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Decoded JWT — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
      .popup-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 50;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
      }
      
      .popup-overlay.active {
        opacity: 1;
        visibility: visible;
      }
      
      .popup-content {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 16px;
        padding: 32px;
        max-width: 500px;
        width: 90%;
        max-height: 90vh;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
        transform: scale(0.9);
        transition: transform 0.3s ease;
        position: relative;
        overflow: hidden;
      }
      
      .popup-overlay.active .popup-content {
        transform: scale(1);
      }
      
      .popup-close {
        position: absolute;
        top: 16px;
        right: 16px;
        background: none;
        border: none;
        color: #94a3b8;
        cursor: pointer;
        font-size: 24px;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: all 0.2s ease;
        z-index: 10;
      }
      
      .popup-close:hover {
        background: rgba(239, 68, 68, 0.2);
        color: #f8fafc;
      }
      
      .content-display {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #475569;
        border-radius: 12px;
        margin: 20px 0;
        position: relative;
        max-height: 300px;
        overflow-y: auto;
        overflow-x: hidden;
      }
      
      .content-text {
        font-family: 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.4;
        color: #e2e8f0;
        white-space: pre-wrap;
        margin: 0;
        padding: 16px;
        word-break: break-all;
        overflow-wrap: anywhere;
      }
      
      .content-display::-webkit-scrollbar {
        width: 8px;
      }
      
      .content-display::-webkit-scrollbar-track {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 4px;
      }
      
      .content-display::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.8);
        border-radius: 4px;
      }
      
      .popup-button {
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.2s ease;
        border: none;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
      }
      
      .popup-button-primary {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
      }
      
      .popup-button-primary:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
      }
      
      .popup-button-secondary {
        background: #475569;
        color: #e2e8f0;
      }
      
      .popup-button-secondary:hover {
        background: #64748b;
      }
    </style>
  </head>
  <body>
    <div id="jwtResultPopup" class="popup-overlay active">
      <div class="popup-content">
        <button class="popup-close" onclick="window.location.href='/'">&times;</button>
        
        <div style="width: 64px; height: 64px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; background: rgba(139, 92, 246, 0.2);">
          <i class="fas fa-file-code text-violet-400 text-2xl"></i>
        </div>
        
        <h3 class="text-xl font-semibold text-center text-violet-300 mb-3">JWT Decoded</h3>
        
        <div class="content-display">
          <pre class="content-text">{{ header }}

{{ payload }}</pre>
        </div>
        
        <div class="flex justify-center gap-3 mt-4">
          <button onclick="copyDecodedJWT()" class="popup-button popup-button-primary">
            <i class="fas fa-copy mr-2"></i> Copy Decoded JWT
          </button>
          <button onclick="window.location.href='/'" class="popup-button popup-button-secondary">
            <i class="fas fa-times mr-2"></i> Close
          </button>
        </div>
      </div>
    </div>
    
    <script>
      function copyDecodedJWT() {
        const jwtText = document.querySelector('.content-text').textContent;
        navigator.clipboard.writeText(jwtText).then(() => {
          const button = event.target.closest('button');
          const originalHTML = button.innerHTML;
          button.innerHTML = `
            <i class="fas fa-check mr-2"></i> Copied!
          `;
          button.classList.add('bg-emerald-600');
          
          setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('bg-emerald-600');
          }, 2000);
        });
      }
    </script>
  </body>
</html>
            """,
            header=header_json,
            payload=payload_json
        )
    except Exception:
        return render_template_string("""
            <p>❌ Decode failed. <a href='{{ url_for("home") }}'>Home</a></p>
            """)

# Admin routes
@app.post("/admin/login")
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == ADMIN_USERNAME and password == ADMIN_KEY:
        resp = make_response(redirect(url_for('home')))
        resp.set_cookie('admin_logged_in', 'true', max_age=86400)  # 1 day
        return resp
    else:
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Login Error — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-md bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-4 text-red-300">Login Failed</h2>
      <p class="text-slate-300 mb-6">Invalid username or password. Please try again.</p>
      <a href="{{ url_for('home') }}" class="block w-full bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium text-center">Back to Home</a>
    </div>
  </body>
</html>
            """
        )

@app.get("/admin/logout")
def admin_logout():
    resp = make_response(redirect(url_for('home')))
    resp.set_cookie('admin_logged_in', '', expires=0)
    return resp

def _is_admin(req: request) -> bool:
    key = req.args.get("key") or req.headers.get("x-admin-key") or req.form.get("key")
    return bool(ADMIN_KEY and key and key == ADMIN_KEY)

@app.get("/admin")
def admin_page():
    if not _is_admin(request):
        return ("Forbidden", 403)
    return render_template_string(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Admin — -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6">
    <div class="w-full max-w-lg bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl">
      <h2 class="text-xl font-semibold mb-2">Admin</h2>
      <p class="text-sm text-slate-300 mb-4">Tokens total: {{ total }} (manual {{ manual }}, auto {{ auto }})</p>
      <form method="post" action="{{ url_for('admin_reset') }}?key={{ key }}" class="space-y-3">
        <div>
          <label class="block text-sm mb-1">JWT token</label>
          <textarea name="jwt" class="w-full bg-slate-900/60 border border-slate-700 rounded px-3 py-2" rows="3" placeholder="Paste any JWT here"></textarea>
        </div>
        <button formaction="{{ url_for('jwt_decode') }}?key={{ key }}" class="bg-sky-600 hover:bg-sky-500 transition-colors rounded px-4 py-2 font-medium" type="submit">Decode JWT</button>
        <button class="bg-rose-600 hover:bg-rose-500 transition-colors rounded px-4 py-2 font-medium">Reset Counters</button>
      </form>
    </div>
  </body>
</html>
        """,
        total=TOKEN_COUNT_TOTAL, manual=TOKEN_COUNT_MANUAL, auto=TOKEN_COUNT_AUTO, key=ADMIN_KEY,
    )

@app.post("/admin/reset")
def admin_reset():
    if not _is_admin(request):
        return ("Forbidden", 403)
    global TOKEN_COUNT_TOTAL, TOKEN_COUNT_MANUAL, TOKEN_COUNT_AUTO, RECENT_EVENTS
    TOKEN_COUNT_TOTAL = 0
    TOKEN_COUNT_MANUAL = 0
    TOKEN_COUNT_AUTO = 0
    RECENT_EVENTS = []
    return redirect(url_for('admin_page', key=ADMIN_KEY))

@app.post("/admin/jwt-decode")
def jwt_decode():
    if not _is_admin(request):
        return ("Forbidden", 403)
    token = (request.form.get('jwt') or '').strip()
    if not token or token.count('.') != 2:
        return render_template_string("""
            <p>❌ Invalid JWT format.</p>
            <p><a href='{{ url_for("admin_page", key=key) }}'>Back</a></p>
            """, key=ADMIN_KEY)
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
        def b64url_decode(data):
            data += '=' * (-len(data) % 4)
            return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8', errors='ignore')
        header_json = b64url_decode(header_b64)
        payload_json = b64url_decode(payload_b64)
        # Mask emails inside
        #header_json = mask_emails_in_text(header_json)
        #payload_json = mask_emails_in_text(payload_json)
        return render_template_string("""
<!doctype html>
<html lang="en"> 
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Decoded JWT</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-900 min-h-screen text-slate-100 grid place-items-center p-6"> 
    <div class="w-full max-w-3xl bg-slate-800/70 border border-slate-700 rounded-xl p-6 shadow-xl space-y-4"> 
      <h2 class="text-xl font-semibold">Decoded JWT</h2>
      <div>
        <div class="text-sm text-slate-400 mb-1">Header</div>
        <pre class="bg-slate-900/60 border border-slate-700 rounded p-3 whitespace-pre-wrap break-words">{{ header }}</pre>
      </div>
      <div>
        <div class="text-sm text-slate-400 mb-1">Payload</div>
        <pre class="bg-slate-900/60 border border-slate-700 rounded p-3 whitespace-pre-wrap break-words">{{ payload }}</pre>
      </div>
      <div class="flex gap-3">
        <a class="bg-slate-700 hover:bg-slate-600 transition-colors rounded px-4 py-2 font-medium" href="{{ url_for('admin_page', key=key) }}">Back</a>
      </div>
    </div>
  </body>
</html>
        """, header=header_json, payload=payload_json, key=ADMIN_KEY)
    except Exception:
        return render_template_string("""
            <p>❌ Decode failed.</p>
            <p><a href='{{ url_for("admin_page", key=key) }}'>Back</a></p>
            """, key=ADMIN_KEY)

# User data storage
user_data = {}

# In-memory token store (not used in web buttons but kept for future)
token_store = {}

def _store_token_and_get_id(token: str) -> str:
    short_id = str(uuid.uuid4()).replace('-', '')[:32]
    token_store[short_id] = {"token": token, "ts": time.time()}
    return short_id

# Global start time and token counters
start_time = time.time()
TOKEN_COUNT_TOTAL = 0
TOKEN_COUNT_AUTO = 0
TOKEN_COUNT_MANUAL = 0
RECENT_EVENTS = []  # list of {mode, email, ts}

def _inc_token_count(mode: str):
    global TOKEN_COUNT_TOTAL, TOKEN_COUNT_AUTO, TOKEN_COUNT_MANUAL
    TOKEN_COUNT_TOTAL += 1
    if mode == "auto":
        TOKEN_COUNT_AUTO += 1
    else:
        TOKEN_COUNT_MANUAL += 1
    try:
        # Keep last 10 events
        if len(RECENT_EVENTS) > 50:
            del RECENT_EVENTS[:len(RECENT_EVENTS)-50]
    except Exception:
        pass

# Optional multi-org configuration via environment variable
# ORG_LIST format: "code1:id1:name1;code2:id2:name2"
def _parse_org_list(env_value: str):
    orgs = []
    if not env_value:
        return orgs
    for entry in env_value.split(";"):
        parts = [p.strip() for p in entry.split(":")]
        if len(parts) >= 2:
            code, oid = parts[0], parts[1]
            name = parts[2] if len(parts) > 2 else "Classplus"
            if code and oid:
                orgs.append({"org_code": code, "org_id": oid, "org_name": name})
    return orgs

ORG_CONFIGS = [
    {"org_code": "ixgioj", "org_id": "735592", "org_name": "Classplus"},
    {"org_code": "zgoxm", "org_id": "896887", "org_name": "OrgA"},
    {"org_code": "wuhki", "org_id": "1681", "org_name": "OrgB"},
    {"org_code": "wfodo", "org_id": "7845", "org_name": "OrgC"},
    {"org_code": "rpsc",  "org_id": "122707", "org_name": "OrgD"},
]

class GmailAliasClient:
    def __init__(self, email_address: str, app_password: str):
        self.email_address = email_address
        self.app_password = app_password
        self.imap_host = "imap.gmail.com"

    def generate_alias(self) -> str:
        local, _, domain = self.email_address.partition("@")
        alias = f"{local}+{random.randint(1000,9999)}@{domain}"
        return alias

    def _connect(self):
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(self.imap_host, 993, ssl_context=context)
        imap.login(self.email_address, self.app_password)
        imap.select("INBOX")
        return imap

    def list_messages(self, to_address: str):
        # Return list of minimal dicts with id/from/subject for messages matching filters
        msgs = []
        imap = self._connect()
        try:
            # Search recent emails first
            status, data = imap.search(None, '(FROM "info@ce.classplus.co")')
            if status != 'OK':
                return []
            ids = (data[0] or b'').split()
            for mid in ids[-20:]:  # check last 20 only
                status, msgdata = imap.fetch(mid, '(RFC822)')
                if status != 'OK' or not msgdata or not msgdata[0]:
                    continue
                msg = email.message_from_bytes(msgdata[0][1])
                to_hdr = msg.get('To', '')
                frm = msg.get('From', '')
                subj = msg.get('Subject', '')
                if to_address.lower() not in to_hdr.lower():
                    continue
                msgs.append({"id": mid.decode(), "from": frm, "subject": subj})
            return msgs
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def read_message(self, message_id: str):
        imap = self._connect()
        try:
            status, msgdata = imap.fetch(message_id, '(RFC822)')
            if status != 'OK' or not msgdata or not msgdata[0]:
                return {"text": "", "html": ""}
            msg = email.message_from_bytes(msgdata[0][1])
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get('Content-Disposition', ''))
                    if ctype == 'text/plain' and 'attachment' not in disp:
                        payload = part.get_payload(decode=True) or b''
                        body_text += payload.decode(errors='ignore')
            else:
                payload = msg.get_payload(decode=True) or b''
                body_text = payload.decode(errors='ignore')
            return {"text": body_text, "html": ""}
        finally:
            try:
                imap.logout()
            except Exception:
                pass

def send_otp_email(email, org_code, org_id, org_name="Classplus"):
    """Send OTP to email"""
    try:
        device_id = str(uuid.uuid4()).replace('-', '')
        headers = {
            "Accept": "application/json, text/plain, */*",
            "region": "IN",
            "Content-Type": "application/json;charset=utf-8",
            "Api-Version": "51",
            "device-id": device_id,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }
        
        otp_payload = {
            'countryExt': '91',
            'orgCode': org_code,
            'viaEmail': '1',
            'email': email,
            'orgId': org_id,
            'otpCount': 0
        }
         
        print(f"[send_otp_email] POST /v2/otp/generate headers={{'device-id': headers.get('device-id'), 'Api-Version': headers.get('Api-Version')}} payload={otp_payload}")
        response = requests.post(f"{apiurl}/v2/otp/generate", json=otp_payload, headers=headers, timeout=20)
        print(f"[send_otp_email] status={response.status_code} body={response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "sessionId" in data["data"]:
                session_id = data['data']['sessionId']
                return {"success": True, "session_id": session_id, "org_id": org_id, "org_name": org_name, "org_code": org_code, "device_id": device_id}
        
        return {"success": False, "error": "OTP send failed"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def verify_otp_email(email, otp, session_id, org_id, device_id, org_code=""):
    """Verify OTP and get token"""
    try:
        device_id_str = str(device_id or str(uuid.uuid4()).replace('-', ''))
        headers = {
            "Accept": "application/json, text/plain, */*",
            "region": "IN",
            "Content-Type": "application/json;charset=utf-8",
            "Api-Version": "51",
            "device-id": device_id_str,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }
        
        fingerprint_id = str(uuid.uuid4()).replace('-', '')
        verify_payload = {
            "otp": otp,
            "countryExt": "91",
            "sessionId": session_id,
            "orgId": org_id,
            "fingerprintId": fingerprint_id,
            "email": email
        }
        print(f"[verify_otp_email] POST /v2/users/verify headers={{'device-id': headers.get('device-id'), 'Api-Version': headers.get('Api-Version')}} payload={verify_payload}")
        response = requests.post(f"{apiurl}/v2/users/verify", json=verify_payload, headers=headers, timeout=20)
        print(f"[verify_otp_email] status={response.status_code} body={response.text[:800]}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and 'token' in data.get('data', {}):
                return {"success": True, "token": data['data']['token']}
        
        # If verification fails, try registration
        if response.status_code in [201, 400, 404, 409]:
            # Indian mobile: starts with 6/7/8/9 and 10 digits total
            first_digit = random.choice(["6", "7", "8", "9"])
            random_mobile = first_digit + "".join([str(random.randint(0,9)) for _ in range(9)])
            random_name_choices = [
                "Anika", "Atharv", "Navya", "Myra", "Aarav", "Ishika",
                "Vihaan", "Aanya", "Kabir", "Prisha", "Advait", "Sia",
                "Arjun", "Ira", "Reyansh", "Anvi", "Krishna", "Aadhya",
                "Vivaan", "Diya", "Rudra", "Meera", "Ayaan", "Kiara"
            ]
            chosen_name = random.choice(random_name_choices)
            register_payload = {
                "contact": {
                    "email": email,
                    "countryExt": "91",
                    "mobile": random_mobile
                },
                "fingerprintId": fingerprint_id,
                "name": chosen_name,
                "orgId": org_id,
                "orgName": "Classplus",
                "orgCode": org_code or "",
                "otp": otp,
                "sessionId": session_id,
                "type": 1,
                "viaEmail": 1,
                "viaSms": 0
            }
            print(f"[verify_otp_email] POST /v2/users/register payload={register_payload}")
            reg_response = requests.post(f"{apiurl}/v2/users/register", json=register_payload, headers=headers, timeout=20)
            print(f"[verify_otp_email] register status={reg_response.status_code} body={reg_response.text[:800]}")
            
            if reg_response.status_code == 200:
                reg_data = reg_response.json()
                if 'token' in reg_data.get('data', {}):
                    return {"success": True, "token": reg_data['data']['token']}
        
        # Try customer verification as fallback
        try:
            customer_headers = {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=utf-8",
            }
            customer_payload = {
                "email": email,
                "otp": otp,
                "countryCode": "+91",
                "userType": 0
            }
            print(f"[verify_otp_email] POST /v2/customer/otp/verify payload={customer_payload}")
            customer_resp = requests.post(f"{apiurl}/v2/customer/otp/verify", json=customer_payload, headers=customer_headers, timeout=20)
            print(f"[verify_otp_email] customer verify status={customer_resp.status_code} body={customer_resp.text[:800]}")
            if customer_resp.status_code == 200:
                customer_data = customer_resp.json()
                token = customer_data.get("data", {}).get("accessToken")
                if token:
                    return {"success": True, "token": token}
        except:
            pass
        
        return {"success": False, "error": "Verification failed"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if 'ORG_LIST' in os.environ and os.environ.get('ORG_LIST'):
    try:
        ORG_CONFIGS = _parse_org_list(os.environ.get('ORG_LIST', ''))
        if not ORG_CONFIGS:
            raise ValueError("empty")
    except Exception:
        ORG_CONFIGS = [
            {"org_code": "ixgioj", "org_id": "735592", "org_name": "Classplus"},
            {"org_code": "zgoxm", "org_id": "896887", "org_name": "OrgA"},
            {"org_code": "wuhki", "org_id": "1681", "org_name": "OrgB"},
            {"org_code": "wfodo", "org_id": "7845", "org_name": "OrgC"},
            {"org_code": "rpsc",  "org_id": "122707", "org_name": "OrgD"},
        ]


def run_flask():
    port_raw = (USER_PORT or os.environ.get("PORT", "10000")).strip()
    try:
        port = int(port_raw or "10000")
    except ValueError:
        port = 10000
    app.run(host="0.0.0.0", port=port)

def main():
    print("╔══════════════════════════════════╗")
    print("║   🚀 -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-  Premium   ║")
    print("║           Premium Edition         ║")
    print("╚══════════════════════════════════╝")
    print("🎯 Starting Web App...")
    print("✨ Enhanced UI Ready!")
    print("🌐 Launching Flask server...")
    run_flask()

if __name__ == "__main__":
    main()
