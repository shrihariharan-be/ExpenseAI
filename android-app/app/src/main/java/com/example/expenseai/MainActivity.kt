package com.example.expenseai

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.webkit.*
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var loadingContainer: LinearLayout
    private lateinit var loadingStatusText: TextView
    private lateinit var errorContainer: LinearLayout
    private lateinit var errorDescription: TextView
    private lateinit var btnRetry: Button
    private lateinit var btnServerSettings: Button

    // Base URL is securely supplied by Gradle BuildConfig (release vs debug)
    private val defaultServerUrl: String get() = BuildConfig.DEFAULT_BASE_URL
    private val isReleaseBuild: Boolean get() = BuildConfig.IS_RELEASE

    // SharedPreferences ONLY stores non-sensitive server endpoint configuration
    private val prefsName = "ExpenseAIServerConfig"
    private val prefsKey = "server_base_url"

    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)
        loadingContainer = findViewById(R.id.loadingContainer)
        loadingStatusText = findViewById(R.id.loadingStatusText)
        errorContainer = findViewById(R.id.errorContainer)
        errorDescription = findViewById(R.id.errorDescription)
        btnRetry = findViewById(R.id.btnRetry)
        btnServerSettings = findViewById(R.id.btnServerSettings)

        val prefs = getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val activeUrl = prefs.getString(prefsKey, defaultServerUrl)?.trim() ?: defaultServerUrl

        setupWebView()
        setupCookieManager()
        setupErrorListeners()

        // Check authentication status and navigate without flashing protected content
        startAppAuthFlow(activeUrl)

        // Native back navigation: Close modals/drawer first, exit on login/register, then webView history, then exit
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (errorContainer.visibility == View.VISIBLE) {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    return
                }

                val currentUrl = webView.url ?: ""
                // When on login or register (fresh install or after logout), Back must exit app, never go into protected pages
                if (currentUrl.contains("/login") || currentUrl.contains("/register")) {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    return
                }

                // Check if web app has an open modal or open navigation drawer
                val jsCheck = "Boolean(window.expenseAI && (window.expenseAI.closeActiveModal() || window.expenseAI.closeActiveDrawer()))"
                webView.evaluateJavascript(jsCheck) { result ->
                    val handledInJs = result == "true"
                    if (!handledInJs) {
                        if (webView.canGoBack()) {
                            webView.goBack()
                        } else {
                            isEnabled = false
                            onBackPressedDispatcher.onBackPressed()
                        }
                    }
                }
            }
        })
    }

    override fun onPause() {
        super.onPause()
        // Ensure authentication session cookies are persistently flushed to storage
        CookieManager.getInstance().flush()
    }

    private fun setupCookieManager() {
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)
    }

    private val isConnecting = java.util.concurrent.atomic.AtomicBoolean(false)

    /**
     * Startup Flow per Production Architecture:
     * 1. Hides WebView during check to prevent flashing protected content.
     * 2. Checks backend availability via /api/health with automatic progressive retry (handling Render cold starts).
     * 3. Shows "Starting secure connection..." -> "Checking secure backend connection..."
     * 4. If waking up -> shows "Server may take a few seconds to wake up (Attempt X of Y)..."
     * 5. If healthy -> checks /api/auth/status:
     *    - Authenticated -> loads /dashboard
     *    - Unauthenticated / Fresh Install -> loads /login
     * 6. If unavailable after retries -> displays friendly error view with "Retry" and "Server Settings".
     *    - Zero stack traces, zero blame on the user.
     */
    private fun startAppAuthFlow(baseUrl: String) {
        if (!isConnecting.compareAndSet(false, true)) {
            return // Already connecting
        }
        errorContainer.visibility = View.GONE
        webView.visibility = View.INVISIBLE
        progressBar.visibility = View.VISIBLE
        loadingContainer.visibility = View.VISIBLE
        loadingStatusText.text = "Starting secure connection..."

        bgExecutor.execute {
            try {
                var isHealthy = false
                val maxRetries = 3 // Total 4 attempts
                var attempt = 0

                mainHandler.post {
                    loadingStatusText.text = "Checking secure backend connection..."
                }

                while (attempt < maxRetries && !isHealthy) {
                    attempt++
                    if (attempt > 1) {
                        mainHandler.post {
                            loadingStatusText.text = "Server may take a few seconds to wake up (Attempt $attempt of $maxRetries)..."
                        }
                        try {
                            Thread.sleep(3500)
                        } catch (ignored: InterruptedException) {}
                    }

                    try {
                        val sanitizedBase = baseUrl.trim().removeSuffix("/")
                        var checkUrl = URL("$sanitizedBase/api/health")
                        var conn = checkUrl.openConnection() as HttpURLConnection
                        conn.connectTimeout = 8000
                        conn.readTimeout = 8000
                        conn.requestMethod = "GET"
                        conn.setRequestProperty("User-Agent", "ExpenseAI-Android-App/2.1")

                        val code = conn.responseCode
                        conn.disconnect()

                        if (code == 200) {
                            isHealthy = true
                        } else if (code == 404) {
                            // Fallback: Check /health
                            checkUrl = URL("$sanitizedBase/health")
                            conn = checkUrl.openConnection() as HttpURLConnection
                            conn.connectTimeout = 6000
                            conn.readTimeout = 6000
                            conn.requestMethod = "GET"
                            conn.setRequestProperty("User-Agent", "ExpenseAI-Android-App/2.1")
                            if (conn.responseCode == 200) {
                                isHealthy = true
                            }
                            conn.disconnect()
                        }
                    } catch (e: Exception) {
                        // Timeout or connection error: retry if attempts remain
                    }
                }

                if (!isHealthy) {
                    mainHandler.post {
                        loadingContainer.visibility = View.GONE
                        progressBar.visibility = View.GONE
                        showErrorView("We're having trouble reaching the server. If starting from cold sleep, tap Retry or configure your address in Server Settings.")
                    }
                    return@execute
                }

            // Backend is healthy! Now check authentication status
            mainHandler.post {
                loadingStatusText.text = "Verifying session..."
            }

            var destinationUrl = "$baseUrl/login"
            try {
                val statusUrl = URL("$baseUrl/api/auth/status")
                val conn = statusUrl.openConnection() as HttpURLConnection
                conn.connectTimeout = 6000
                conn.readTimeout = 6000
                conn.requestMethod = "GET"
                conn.setRequestProperty("User-Agent", "ExpenseAI-Android-App/2.0")

                // Forward session cookies from native CookieManager
                val cookieManager = CookieManager.getInstance()
                val cookies = cookieManager.getCookie(baseUrl)
                if (!cookies.isNullOrBlank()) {
                    conn.setRequestProperty("Cookie", cookies)
                }

                val code = conn.responseCode
                if (code == 200) {
                    val responseText = conn.inputStream.bufferedReader().readText()
                    val json = org.json.JSONObject(responseText)
                    val isAuthenticated = json.optBoolean("authenticated", false)
                    destinationUrl = if (isAuthenticated) {
                        "$baseUrl/dashboard"
                    } else {
                        "$baseUrl/login"
                    }
                } else {
                    destinationUrl = "$baseUrl/login"
                }
                conn.disconnect()
            } catch (e: Exception) {
                // Default to login on any auth status read anomaly
                destinationUrl = "$baseUrl/login"
            }

            mainHandler.post {
                loadingContainer.visibility = View.GONE
                webView.visibility = View.VISIBLE
                progressBar.visibility = View.VISIBLE
                webView.loadUrl(destinationUrl)
            }
        } finally {
            isConnecting.set(false)
        }
    }
}

    private fun setupErrorListeners() {
        btnRetry.setOnClickListener {
            val prefs = getSharedPreferences(prefsName, Context.MODE_PRIVATE)
            val currentUrl = prefs.getString(prefsKey, defaultServerUrl) ?: defaultServerUrl
            startAppAuthFlow(currentUrl)
        }

        btnServerSettings.setOnClickListener {
            showServerSettingsDialog()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val settings = webView.settings

        // Mandatory Security Hardening per Production Audit
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.setGeolocationEnabled(false)

        if (isReleaseBuild) {
            // Strict HTTPS - Never allow mixed or downgraded HTTP content in production
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.safeBrowsingEnabled = true
        }

        // Web App Feature enablement
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true
        settings.textZoom = 100
        settings.cacheMode = WebSettings.LOAD_DEFAULT

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                // If page finished successfully, hide error container
                if (errorContainer.visibility == View.VISIBLE && url != null && !url.startsWith("data:")) {
                    errorContainer.visibility = View.GONE
                }
                webView.visibility = View.VISIBLE

                // Clear history when arriving at login or register (e.g. after logout or fresh install)
                // so pressing Android Back can NEVER navigate back to protected pages!
                if (url != null && (url.contains("/login") || url.contains("/register"))) {
                    view?.clearHistory()
                }

                injectMobileResponsiveFix(view)
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url ?: return false
                val scheme = url.scheme?.lowercase() ?: ""

                // Strict security: Reject file://, content://, javascript:
                if (scheme == "file" || scheme == "content" || scheme == "javascript") {
                    return true // Block navigation
                }

                // In release mode, reject navigation downgrades to unencrypted HTTP
                if (isReleaseBuild && scheme == "http") {
                    Toast.makeText(this@MainActivity, "Insecure HTTP connection blocked in release mode.", Toast.LENGTH_SHORT).show()
                    return true
                }

                // If link points to an external site or mailto/tel, launch in external app
                val host = url.host ?: ""
                val currentHost = Uri.parse(webView.url ?: defaultServerUrl).host ?: ""
                if (host.isNotEmpty() && currentHost.isNotEmpty() && !host.equals(currentHost, ignoreCase = true)) {
                    try {
                        val intent = Intent(Intent.ACTION_VIEW, url)
                        startActivity(intent)
                        return true
                    } catch (_: Exception) {}
                }

                return false
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    progressBar.visibility = View.GONE
                    showErrorView()
                }
            }

            override fun onReceivedHttpError(
                view: WebView?,
                request: WebResourceRequest?,
                errorResponse: WebResourceResponse?
            ) {
                if (request?.isForMainFrame == true) {
                    val statusCode = errorResponse?.statusCode ?: 0
                    if (statusCode >= 500) {
                        progressBar.visibility = View.GONE
                        showErrorView()
                    }
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress
                if (newProgress >= 100) {
                    progressBar.visibility = View.GONE
                }
            }
        }
    }

    private fun showErrorView(message: String = "We're having trouble reaching the server.") {
        loadingContainer.visibility = View.GONE
        webView.visibility = View.GONE
        errorContainer.visibility = View.VISIBLE
        errorDescription.text = message
    }

    private fun showServerSettingsDialog() {
        val prefs = getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val currentUrl = prefs.getString(prefsKey, defaultServerUrl) ?: defaultServerUrl

        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_server_settings, null)
        val editServerUrl = dialogView.findViewById<EditText>(R.id.editServerUrl)
        val btnTest = dialogView.findViewById<Button>(R.id.btnTestConnection)
        val txtStatus = dialogView.findViewById<TextView>(R.id.txtTestStatus)

        editServerUrl.setText(currentUrl)

        btnTest.setOnClickListener {
            val candidateUrl = editServerUrl.text.toString().trim()
            val validatedUrl = validateAndSanitizeUrl(candidateUrl)
            if (validatedUrl == null) {
                val reqMsg = if (isReleaseBuild) "Requires a valid HTTPS address (e.g. https://expenseai.onrender.com)" else "Requires a valid HTTP or HTTPS address"
                txtStatus.setTextColor(Color.parseColor("#EF4444"))
                txtStatus.text = "❌ Invalid URL: $reqMsg"
                return@setOnClickListener
            }

            txtStatus.setTextColor(Color.parseColor("#64748B"))
            txtStatus.text = "⏳ Testing connectivity to $validatedUrl..."
            btnTest.isEnabled = false

            bgExecutor.execute {
                var success = false
                var resultMsg = ""
                try {
                    var healthUrl = URL("$validatedUrl/api/health")
                    var conn = healthUrl.openConnection() as HttpURLConnection
                    conn.connectTimeout = 8000
                    conn.readTimeout = 8000
                    conn.requestMethod = "GET"
                    conn.setRequestProperty("User-Agent", "ExpenseAI-Android-App/2.0")

                    var code = conn.responseCode
                    conn.disconnect()

                    if (code == 200) {
                        success = true
                        resultMsg = "✅ Connection Successful! Backend is healthy (HTTP 200)."
                    } else if (code == 404) {
                        val altUrl = URL("$validatedUrl/health")
                        val altConn = altUrl.openConnection() as HttpURLConnection
                        altConn.connectTimeout = 6000
                        altConn.readTimeout = 6000
                        if (altConn.responseCode == 200) {
                            success = true
                            resultMsg = "✅ Connection Successful! Backend is healthy (HTTP 200 via /health)."
                        } else {
                            resultMsg = "⚠️ Server responded with HTTP status $code."
                        }
                        altConn.disconnect()
                    } else {
                        resultMsg = "⚠️ Server responded with HTTP status $code."
                    }
                } catch (e: Exception) {
                    resultMsg = "❌ Connection failed: ${e.localizedMessage ?: "Connection timed out"}"
                }

                mainHandler.post {
                    btnTest.isEnabled = true
                    if (success) {
                        txtStatus.setTextColor(Color.parseColor("#10B981"))
                    } else {
                        txtStatus.setTextColor(Color.parseColor("#EF4444"))
                    }
                    txtStatus.text = resultMsg
                }
            }
        }

        AlertDialog.Builder(this)
            .setTitle("Server Settings")
            .setView(dialogView)
            .setPositiveButton("Save") { _, _ ->
                val enteredUrl = editServerUrl.text.toString().trim()
                val validated = validateAndSanitizeUrl(enteredUrl)
                if (validated != null) {
                    prefs.edit().putString(prefsKey, validated).apply()
                    startAppAuthFlow(validated)
                } else {
                    Toast.makeText(this, "URL not saved: invalid address", Toast.LENGTH_LONG).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .setNeutralButton("Reset Default") { _, _ ->
                prefs.edit().putString(prefsKey, defaultServerUrl).apply()
                startAppAuthFlow(defaultServerUrl)
            }
            .show()
    }

    /**
     * URL Validation & Sanitization per Security Audit:
     * - Validates URI syntax.
     * - In release mode: Requires HTTPS.
     * - Rejects file://, content://, javascript:, malformed hostnames.
     */
    private fun validateAndSanitizeUrl(rawUrl: String): String? {
        if (rawUrl.isBlank()) return null
        var candidate = rawUrl.trim().removeSuffix("/")
        if (!candidate.startsWith("http://", ignoreCase = true) && !candidate.startsWith("https://", ignoreCase = true)) {
            candidate = "https://$candidate"
        }
        return try {
            val uri = URI(candidate)
            val scheme = uri.scheme?.lowercase() ?: return null
            val host = uri.host ?: return null

            if (isReleaseBuild) {
                // Strict production requirement: HTTPS only
                if (scheme != "https") return null
            } else {
                if (scheme != "http" && scheme != "https") return null
            }

            if (host.isBlank()) return null

            uri.toASCIIString().removeSuffix("/")
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Mobile Responsive Injection Engine:
     * Injects responsive styles on narrow viewports (<768px):
     * - Fixes Expenses heading & action buttons overlap
     * - Stacks Add Expense / Auto-Categorize buttons cleanly below title with max-width: 320px
     * - Horizontally scrolls tables without breaking page viewport
     * - Scales Quick Stats and sets comfortable touch targets (44px min-height)
     * - Handles footer safe-area padding
     */
    private fun injectMobileResponsiveFix(view: WebView?) {
        val js = """
            (function() {
                var cssId = 'expenseai-mobile-responsive-fix';
                if (!document.getElementById(cssId)) {
                    var style = document.createElement('style');
                    style.id = cssId;
                    style.type = 'text/css';
                    style.innerHTML = `
                        @media (max-width: 768px) {
                            html, body {
                                overflow-x: hidden !important;
                                max-width: 100vw !important;
                                width: 100% !important;
                                box-sizing: border-box !important;
                            }
                            body {
                                padding-bottom: max(env(safe-area-inset-bottom, 0px), 24px) !important;
                            }
                            .navbar, nav.navbar, header.top-navbar {
                                padding-left: 12px !important;
                                padding-right: 12px !important;
                            }
                            .card-header,
                            .card-header.d-flex,
                            .d-flex.justify-content-between.align-items-center,
                            .expenses-header,
                            .page-header,
                            div:has(> h1, > h2, > h3):has(> button, > div > button, > a.btn) {
                                display: flex !important;
                                flex-direction: column !important;
                                align-items: flex-start !important;
                                width: 100% !important;
                                gap: 12px !important;
                                margin-bottom: 16px !important;
                            }
                            h1, h2, h3, .page-title, .navbar-page-title, #expenses-title {
                                width: 100% !important;
                                display: block !important;
                                margin: 0 0 8px 0 !important;
                                font-size: 1.65rem !important;
                                font-weight: 700 !important;
                                line-height: 1.25 !important;
                                word-break: break-word !important;
                            }
                            .card-header > .d-flex,
                            .d-flex.justify-content-between.align-items-center > div:has(> button),
                            div:has(> #add-expense),
                            .header-actions {
                                display: flex !important;
                                flex-direction: column !important;
                                width: 100% !important;
                                max-width: 320px !important;
                                gap: 8px !important;
                                margin: 0 !important;
                            }
                            #add-expense, #categorize-expenses,
                            .card-header .btn,
                            .d-flex.justify-content-between.align-items-center button.btn,
                            .d-flex.justify-content-between.align-items-center a.btn,
                            .btn-action-mobile {
                                width: 100% !important;
                                max-width: 320px !important;
                                min-height: 44px !important;
                                font-size: 0.95rem !important;
                                font-weight: 600 !important;
                                padding: 10px 16px !important;
                                border-radius: 8px !important;
                                display: inline-flex !important;
                                align-items: center !important;
                                justify-content: center !important;
                                gap: 8px !important;
                                margin: 4px 0 !important;
                                touch-action: manipulation !important;
                                box-sizing: border-box !important;
                            }
                            .table-responsive,
                            div:has(> table),
                            .table-container {
                                overflow-x: auto !important;
                                -webkit-overflow-scrolling: touch !important;
                                width: 100% !important;
                                max-width: 100% !important;
                                margin-bottom: 20px !important;
                                border-radius: 8px !important;
                                display: block !important;
                            }
                            table, .table {
                                min-width: 520px !important;
                                margin-bottom: 0 !important;
                            }
                            table th, table td {
                                padding: 10px 8px !important;
                                font-size: 0.85rem !important;
                                white-space: nowrap !important;
                                vertical-align: middle !important;
                            }
                            .card, .quick-stats, div:has(> .card-header) {
                                width: 100% !important;
                                max-width: 100% !important;
                                margin: 16px 0 !important;
                                border-radius: 12px !important;
                                box-sizing: border-box !important;
                            }
                            .card-body {
                                padding: 16px !important;
                            }
                            input[type="month"], #month-filter, .form-control {
                                min-height: 44px !important;
                                font-size: 0.95rem !important;
                                width: 100% !important;
                            }
                            .card-body h3, .card-body .display-6, .card-body strong {
                                font-size: 1.65rem !important;
                                word-break: break-all !important;
                            }
                            footer, .footer, footer .container, .app-footer {
                                padding: 24px 16px max(env(safe-area-inset-bottom, 0px), 32px) 16px !important;
                                white-space: normal !important;
                                word-wrap: break-word !important;
                                text-align: center !important;
                                font-size: 0.8rem !important;
                                line-height: 1.6 !important;
                                display: block !important;
                            }
                            footer a, .app-footer a {
                                display: inline-block !important;
                                padding: 4px 6px !important;
                                text-decoration: underline !important;
                            }
                        }
                    `;
                    document.head.appendChild(style);
                }
                var vp = document.querySelector('meta[name="viewport"]');
                if (!vp) {
                    vp = document.createElement('meta');
                    vp.name = 'viewport';
                    document.head.appendChild(vp);
                }
                vp.content = 'width=device-width, initial-scale=1.0, maximum-scale=5.0, viewport-fit=cover';
            })();
        """.trimIndent()
        view?.evaluateJavascript(js, null)
    }
}
