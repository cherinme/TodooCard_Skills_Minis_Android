package io.github.jiqimaooo.todoocard.androidbridge;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.util.SparseArray;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@SuppressLint("MissingPermission") // Every BLE operation is gated by hasPermissions().
public final class MainActivity extends Activity {
    private static final String TAG = "TodooCardBridge";
    private static final int PERMISSION_REQUEST = 1001;
    private static final int MANUFACTURER_ID = 0x5053;
    private static final int SCREEN_TYPE = 0x134C;
    private static final int WIDTH = 528;
    private static final int HEIGHT = 792;
    private static final int DESIRED_MTU = 247;
    private static final long NO_RESPONSE_PACE_MS = 12;
    private static final long QUEUE_RETRY_MS = 6;
    private static final long QUEUE_BUSY_TIMEOUT_MS = 10_000;
    private static final UUID SERVICE_FEF0 = uuid16("FEF0");
    private static final UUID SERVICE_FDF0 = uuid16("FDF0");
    private static final UUID CONTROL_FEF1 = uuid16("FEF1");
    private static final UUID CONTROL_FDF1 = uuid16("FDF1");
    private static final UUID DATA_FEF2 = uuid16("FEF2");
    private static final UUID DATA_FDF2 = uuid16("FDF2");
    private static final UUID BATTERY_SERVICE = uuid16("180F");
    private static final UUID BATTERY_LEVEL = uuid16("2A19");
    private static final UUID CLIENT_CONFIG = uuid16("2902");

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, JSONObject> listedDevices = new LinkedHashMap<>();
    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothDevice targetDevice;
    private BluetoothGattCharacteristic controlCharacteristic;
    private BluetoothGattCharacteristic dataCharacteristic;
    private LinearLayout content;
    private TextView output;
    private Button actionButton;
    private String mode;
    private String requestId;
    private String targetAddress;
    private String callbackBaseUrl;
    private byte[] payload;
    private LocationManager locationManager;
    private Advertisement advertisement;
    private boolean resultWritten;
    private boolean secureLinkVerified;
    private boolean notificationsReady;
    private boolean transferStarted;
    private boolean streaming;
    private boolean dataWriteWithResponse;
    private boolean pairingHintShown;
    private boolean backgroundExecutionStarted;
    private boolean serviceDiscoveryStarted;
    private boolean directBondedConnection;
    private int blockPayloadSize;
    private int nextBlock;
    private int lastProgress = -1;
    private int negotiatedMtu = 23;
    private long queueBusySince;
    private long transferStartedAt;
    private long payloadWrittenAt;
    private Runnable operationTimeout;
    private Runnable controlTimeout;
    private Runnable finalAckTimeout;
    private Runnable mtuFallback;
    private Runnable dataWriteTimeout;
    private final Runnable dataPump = this::pumpData;
    private final LocationListener locationListener = new LocationListener() {
        @Override
        public void onLocationChanged(Location location) {
            finishLocation(location);
        }

        @Override
        public void onProviderEnabled(String provider) {
        }

        @Override
        public void onProviderDisabled(String provider) {
        }

        @Override
        public void onStatusChanged(String provider, int status, Bundle extras) {
        }
    };

    private static UUID uuid16(String value) {
        return UUID.fromString("0000" + value + "-0000-1000-8000-00805F9B34FB");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setWindowAnimations(0);
        buildUi();
        BluetoothManager manager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        adapter = manager == null ? null : manager.getAdapter();
        IntentFilter filter = new IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED);
        registerReceiver(bondReceiver, filter);
        begin(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        begin(intent);
    }

    @Override
    protected void onDestroy() {
        cleanupBluetooth();
        cleanupLocation();
        BridgeForegroundService.stop(this);
        try {
            unregisterReceiver(bondReceiver);
        } catch (IllegalArgumentException ignored) {
        }
        super.onDestroy();
    }

    private void buildUi() {
        output = new TextView(this);
        output.setTextSize(15);
        output.setTextColor(0xff202124);
        output.setPadding(36, 36, 36, 36);
        output.setGravity(Gravity.START);
        actionButton = new Button(this);
        actionButton.setText(R.string.trust_minis);
        actionButton.setVisibility(View.GONE);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(output);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setBackgroundColor(0xffffffff);
        content.setVisibility(View.INVISIBLE);
        content.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        content.addView(actionButton, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        setContentView(content);
    }

    private void begin(Intent intent) {
        cleanupBluetooth();
        cleanupLocation();
        handler.removeCallbacksAndMessages(null);
        listedDevices.clear();
        resultWritten = false;
        secureLinkVerified = false;
        notificationsReady = false;
        transferStarted = false;
        streaming = false;
        dataWriteWithResponse = false;
        pairingHintShown = false;
        serviceDiscoveryStarted = false;
        directBondedConnection = false;
        blockPayloadSize = 0;
        nextBlock = 0;
        lastProgress = -1;
        negotiatedMtu = 23;
        queueBusySince = 0;
        transferStartedAt = 0;
        payloadWrittenAt = 0;
        backgroundExecutionStarted = false;
        output.setText("");
        content.setVisibility(View.INVISIBLE);
        actionButton.setVisibility(View.GONE);
        actionButton.setOnClickListener(null);

        Uri uri = intent.getData();
        if (uri == null || !"todoocard-minis".equals(uri.getScheme())
                || !"bridge".equals(uri.getHost()) || !"/run".equals(uri.getPath())) {
            showInteractiveUi();
            log("Launch this bridge from the todoocard skill inside Minis for Android.");
            return;
        }
        String port = uri.getQueryParameter("port");
        String token = uri.getQueryParameter("token");
        if (port == null || !port.matches("[0-9]{2,5}")
                || token == null || !token.matches("[0-9a-f]{48}")) {
            showInteractiveUi();
            log("Rejected an invalid local bridge request.");
            return;
        }
        callbackBaseUrl = "http://127.0.0.1:" + port + "/" + token;
        log("Connecting to the active Minis request...");
        new Thread(this::fetchRequest, "todoocard-request").start();
    }

    private void fetchRequest() {
        try {
            JSONObject request = new JSONObject(new String(httpGet("request", 64 * 1024), StandardCharsets.UTF_8));
            byte[] requestedPayload = null;
            if ("send".equals(request.optString("mode"))) {
                requestedPayload = httpGet("payload", 1_000_000);
            }
            byte[] finalPayload = requestedPayload;
            handler.post(() -> startOperation(request, finalPayload));
        } catch (Exception error) {
            handler.post(() -> {
                showInteractiveUi();
                log("FAILED: Cannot read the Minis request: " + error.getMessage());
            });
        }
    }

    private void startOperation(JSONObject request, byte[] requestedPayload) {
        mode = request.optString("mode", null);
        requestId = request.optString("request_id", null);
        targetAddress = request.optString("device_id", null);
        if (mode == null || requestId == null) {
            showInteractiveUi();
            log("FAILED: Minis request is missing mode or request_id.");
            return;
        }
        if (!Arrays.asList("scan", "pair", "probe", "send", "location").contains(mode)) {
            fail("Unsupported mode: " + mode);
            return;
        }
        if (Arrays.asList("pair", "probe", "send").contains(mode)
                && (targetAddress == null || !targetAddress.matches("(?i)([0-9a-f]{2}:){5}[0-9a-f]{2}"))) {
            fail("An exact BLE MAC address is required");
            return;
        }
        String suppliedKey = request.optString("companion_key", "");
        if (!suppliedKey.matches("[0-9a-f]{64}")) {
            fail("Minis request is missing a valid local trust key");
            return;
        }
        String trustedKey = getSharedPreferences("trust", MODE_PRIVATE)
                .getString("companion_key", "");
        if (trustedKey.isEmpty()) {
            showInteractiveUi();
            log("First connection from Minis. Approve only if you just started a TodooCard command.");
            actionButton.setVisibility(View.VISIBLE);
            actionButton.setOnClickListener(view -> {
                getSharedPreferences("trust", MODE_PRIVATE).edit()
                        .putString("companion_key", suppliedKey).apply();
                actionButton.setVisibility(View.GONE);
                log("This Minis runtime is now trusted. Clear companion app data to reset trust.");
                continueOperation(requestedPayload);
            });
            return;
        }
        if (!MessageDigest.isEqual(
                trustedKey.getBytes(StandardCharsets.US_ASCII),
                suppliedKey.getBytes(StandardCharsets.US_ASCII))) {
            fail("This request does not match the trusted Minis runtime");
            return;
        }
        continueOperation(requestedPayload);
    }

    private void continueOperation(byte[] requestedPayload) {
        if ("send".equals(mode)) {
            try {
                payload = requestedPayload;
                validatePayload(payload);
                log("Validated payload: " + payload.length + " bytes");
            } catch (Exception error) {
                fail("Cannot load validated payload: " + error.getMessage());
                return;
            }
        }
        if ("location".equals(mode)) {
            if (!hasPermissions()) {
                showInteractiveUi();
                requestPermissions(requiredPermissions(), PERMISSION_REQUEST);
                log("Waiting for Android location permission");
                return;
            }
            if (!startBackgroundExecution()) {
                return;
            }
            startLocation();
            return;
        }
        if (adapter == null) {
            fail("Bluetooth LE is unavailable on this Android device");
            return;
        }
        if (!adapter.isEnabled()) {
            fail("Enable Bluetooth on the Android device first");
            return;
        }
        if (!hasPermissions()) {
            showInteractiveUi();
            requestPermissions(requiredPermissions(), PERMISSION_REQUEST);
            log("Waiting for Android Bluetooth permission");
            return;
        }
        if (!startBackgroundExecution()) {
            return;
        }
        if ("probe".equals(mode) || "send".equals(mode)) {
            connectBondedTarget();
        } else {
            startScan();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != PERMISSION_REQUEST) {
            return;
        }
        if (!hasPermissions()) {
            fail("Required Android permission was denied");
            return;
        }
        if (!startBackgroundExecution()) {
            return;
        }
        if ("location".equals(mode)) {
            startLocation();
        } else if ("probe".equals(mode) || "send".equals(mode)) {
            connectBondedTarget();
        } else {
            startScan();
        }
    }

    private void showInteractiveUi() {
        content.setVisibility(View.VISIBLE);
    }

    private boolean startBackgroundExecution() {
        if (backgroundExecutionStarted) {
            return true;
        }
        try {
            BridgeForegroundService.start(this, mode);
        } catch (RuntimeException error) {
            showInteractiveUi();
            fail("Cannot start the Android foreground operation: " + error.getMessage());
            return false;
        }
        backgroundExecutionStarted = true;
        content.setVisibility(View.INVISIBLE);
        handler.postDelayed(() -> moveTaskToBack(true), 200);
        return true;
    }

    private String[] requiredPermissions() {
        if ("location".equals(mode)) {
            return new String[]{Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION};
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return new String[]{Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT};
        }
        return new String[]{Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION};
    }

    private boolean hasPermissions() {
        if ("location".equals(mode)) {
            return checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
                    || checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        }
        for (String permission : requiredPermissions()) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    private void startLocation() {
        try {
            locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
            if (locationManager == null) {
                fail("Android location service is unavailable");
                return;
            }
            Location best = null;
            for (String provider : locationManager.getProviders(true)) {
                Location known = locationManager.getLastKnownLocation(provider);
                if (known != null && (best == null || known.getAccuracy() < best.getAccuracy())) {
                    best = known;
                }
                locationManager.requestLocationUpdates(provider, 0, 0, locationListener, Looper.getMainLooper());
            }
            Location fallback = best;
            operationTimeout = () -> {
                if (fallback != null && System.currentTimeMillis() - fallback.getTime() <= 15 * 60_000L) {
                    finishLocation(fallback);
                } else {
                    fail("Timed out waiting for an Android location fix");
                }
            };
            handler.postDelayed(operationTimeout, 25_000);
            log("Waiting for the current Android location");
        } catch (SecurityException error) {
            fail("Android location permission error: " + error.getMessage());
        }
    }

    private void finishLocation(Location location) {
        if (resultWritten || !"location".equals(mode)) {
            return;
        }
        if (System.currentTimeMillis() - location.getTime() > 15 * 60_000L) {
            log("Ignoring a stale Android location fix");
            return;
        }
        if (operationTimeout != null) {
            handler.removeCallbacks(operationTimeout);
        }
        JSONObject extra = new JSONObject();
        try {
            extra.put("latitude", location.getLatitude());
            extra.put("longitude", location.getLongitude());
            extra.put("accuracy_m", location.getAccuracy());
            extra.put("provider", location.getProvider());
            extra.put("timestamp_ms", location.getTime());
        } catch (JSONException ignored) {
        }
        succeed("Android location acquired", extra);
    }

    private void startScan() {
        try {
            scanner = adapter.getBluetoothLeScanner();
            if (scanner == null) {
                fail("Android BLE scanner is unavailable");
                return;
            }
            ScanSettings settings = new ScanSettings.Builder()
                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                    .build();
            scanner.startScan(null, settings, scanCallback);
            log("scan".equals(mode) ? "Scanning compatible TodooCard devices for 15 seconds" : "Scanning exact target " + targetAddress);
            if ("scan".equals(mode)) {
                operationTimeout = this::finishList;
                handler.postDelayed(operationTimeout, 15_000);
            } else {
                operationTimeout = () -> fail("Timed out scanning for exact target " + targetAddress);
                handler.postDelayed(operationTimeout, "pair".equals(mode) ? 75_000 : 45_000);
            }
        } catch (SecurityException error) {
            fail("Bluetooth permission error: " + error.getMessage());
        }
    }

    private void connectBondedTarget() {
        try {
            BluetoothDevice bondedTarget = null;
            for (BluetoothDevice candidate : adapter.getBondedDevices()) {
                if (candidate.getAddress().equalsIgnoreCase(targetAddress)) {
                    bondedTarget = candidate;
                    break;
                }
            }
            if (bondedTarget == null) {
                fail("Target is not in Android bonded devices; run pair, then probe --save");
                return;
            }
            targetDevice = bondedTarget;
            directBondedConnection = true;
            advertisement = new Advertisement(SCREEN_TYPE, -1, true, false);
            log("Using existing Android bond for direct connection to " + targetAddress);
            connectTarget();
        } catch (SecurityException error) {
            fail("Bluetooth bonded-device permission error: " + error.getMessage());
        }
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            Advertisement info = parseAdvertisement(result);
            if (info == null || info.screenType != SCREEN_TYPE) {
                return;
            }
            BluetoothDevice device = result.getDevice();
            String address;
            String name;
            try {
                address = device.getAddress().toUpperCase(Locale.ROOT);
                name = device.getName();
            } catch (SecurityException error) {
                fail("Bluetooth permission error: " + error.getMessage());
                return;
            }
            if ("scan".equals(mode)) {
                try {
                    JSONObject item = new JSONObject();
                    item.put("name", name == null ? "" : name);
                    item.put("address", address);
                    item.put("rssi", result.getRssi());
                    item.put("screen", String.format(Locale.ROOT, "0x%04X", info.screenType));
                    item.put("firmware", String.format(Locale.ROOT, "0x%02X", info.firmware));
                    item.put("secure", info.secure);
                    item.put("pairing", info.pairingOpen ? "open" : "closed");
                    boolean firstObservation = !listedDevices.containsKey(address);
                    listedDevices.put(address, item);
                    if (firstObservation) {
                        log(String.format(Locale.ROOT, "%s address=%s RSSI=%d secure=%s pairing=%s",
                                name == null ? "(no name)" : name, address, result.getRssi(), info.secure, info.pairingOpen ? "open" : "closed"));
                    }
                } catch (JSONException error) {
                    fail("Cannot record scan result");
                }
                return;
            }
            if (!address.equalsIgnoreCase(targetAddress)) {
                return;
            }
            if ("pair".equals(mode)) {
                if (!info.secure) {
                    fail("Target firmware does not advertise the secure pairing protocol");
                    return;
                }
                if (!info.pairingOpen) {
                    if (!pairingHintShown) {
                        pairingHintShown = true;
                        log("Exact target found with pairing=closed; keep holding the rear button until the light fast-flashes");
                    }
                    return;
                }
            } else if (info.pairingOpen) {
                fail("Refusing probe/send while the new-device pairing window is open");
                return;
            }
            stopScan();
            handler.removeCallbacks(operationTimeout);
            advertisement = info;
            targetDevice = device;
            log("Advertisement verified: manufacturer=0x5053 screen=0x134C secure=" + info.secure);
            if ("pair".equals(mode) && device.getBondState() != BluetoothDevice.BOND_BONDED) {
                log("Starting Android system bond; accept any system pairing prompt");
                if (!device.createBond()) {
                    fail("Android refused to start the system bond");
                }
                return;
            }
            connectTarget();
        }

        @Override
        public void onScanFailed(int errorCode) {
            fail("Android BLE scan failed with code " + errorCode);
        }
    };

    private final BroadcastReceiver bondReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            BluetoothDevice device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
            if (targetDevice == null || device == null || !targetDevice.getAddress().equals(device.getAddress())) {
                return;
            }
            int state = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.ERROR);
            if (state == BluetoothDevice.BOND_BONDED) {
                log("Android system bond created; verifying encrypted Battery Level");
                connectTarget();
            } else if (state == BluetoothDevice.BOND_NONE) {
                fail("Android system bonding failed or was cancelled");
            }
        }
    };

    private Advertisement parseAdvertisement(ScanResult result) {
        if (result.getScanRecord() == null) {
            return null;
        }
        SparseArray<byte[]> data = result.getScanRecord().getManufacturerSpecificData();
        byte[] value = data == null ? null : data.get(MANUFACTURER_ID);
        if (value == null || value.length < 5) {
            return null;
        }
        int screen = (value[0] & 0xff) | ((value[4] & 0xff) << 8);
        int flags = value[1] & 0xff;
        int firmware = value[2] & 0xff;
        boolean secure = screen == SCREEN_TYPE && firmware >= 0x8c && (flags & 0x01) != 0;
        return new Advertisement(screen, firmware, secure, secure && (flags & 0x02) != 0);
    }

    private void connectTarget() {
        try {
            log("Connecting to " + targetAddress);
            gatt = targetDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
            operationTimeout = () -> fail("Timed out connecting to target");
            handler.postDelayed(operationTimeout, directBondedConnection ? 45_000 : 20_000);
        } catch (SecurityException error) {
            fail("Bluetooth connect permission error: " + error.getMessage());
        }
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt callbackGatt, int status, int newState) {
            handler.post(() -> {
                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    handler.removeCallbacks(operationTimeout);
                    boolean highPriority = callbackGatt.requestConnectionPriority(
                            BluetoothGatt.CONNECTION_PRIORITY_HIGH);
                    log("Connected; high-priority connection request=" + highPriority);
                    operationTimeout = () -> fail("Timed out preparing the verified TodooCard GATT connection");
                    handler.postDelayed(operationTimeout, 35_000);
                    if (callbackGatt.requestMtu(DESIRED_MTU)) {
                        log("Requesting GATT MTU " + DESIRED_MTU);
                        mtuFallback = () -> beginServiceDiscovery(callbackGatt, negotiatedMtu);
                        handler.postDelayed(mtuFallback, 5_000);
                    } else {
                        log("MTU request was not accepted; using the current MTU");
                        beginServiceDiscovery(callbackGatt, negotiatedMtu);
                    }
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED && !resultWritten) {
                    fail("BLE disconnected before completion; full-frame retry required (status " + status + ")");
                }
            });
        }

        @Override
        public void onMtuChanged(BluetoothGatt callbackGatt, int mtu, int status) {
            handler.post(() -> {
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    negotiatedMtu = mtu;
                }
                beginServiceDiscovery(callbackGatt, negotiatedMtu);
            });
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt callbackGatt, int status) {
            handler.post(() -> {
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    fail("Service discovery failed with status " + status);
                    return;
                }
                if (advertisement.secure && !secureLinkVerified) {
                    BluetoothGattService battery = callbackGatt.getService(BATTERY_SERVICE);
                    BluetoothGattCharacteristic level = battery == null ? null : battery.getCharacteristic(BATTERY_LEVEL);
                    if (level == null) {
                        fail("Encrypted Battery Level is missing; cannot verify the Android bond");
                    } else {
                        log("Reading encrypted Battery Level to verify the system bond");
                        if (!callbackGatt.readCharacteristic(level)) {
                            fail("Android refused the encrypted Battery Level read");
                        }
                    }
                    return;
                }
                prepareImageService();
            });
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic, int status) {
            handler.post(() -> {
                if (!BATTERY_LEVEL.equals(characteristic.getUuid())) {
                    return;
                }
                byte[] value = characteristic.getValue();
                if (status != BluetoothGatt.GATT_SUCCESS || value == null || value.length != 1) {
                    fail("Encrypted pairing verification failed with status " + status);
                    return;
                }
                secureLinkVerified = true;
                log("Encrypted link verified; battery=" + (value[0] & 0xff) + "%");
                if ("pair".equals(mode)) {
                    succeed("Android system bond is ready; run probe separately", null);
                } else {
                    prepareImageService();
                }
            });
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt callbackGatt, BluetoothGattDescriptor descriptor, int status) {
            handler.post(() -> {
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    fail("Enabling control notifications failed with status " + status);
                    return;
                }
                notificationsReady = true;
                log("Control notifications enabled");
                handler.postDelayed(MainActivity.this::beginTransfer, 400);
            });
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic) {
            byte[] value = characteristic.getValue();
            byte[] notification = value == null ? null : Arrays.copyOf(value, value.length);
            handler.post(() -> handleControl(notification));
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic, int status) {
            handler.post(() -> {
                boolean isDataWrite = dataCharacteristic != null
                        && characteristic.getUuid().equals(dataCharacteristic.getUuid());
                if (isDataWrite && dataWriteTimeout != null) {
                    handler.removeCallbacks(dataWriteTimeout);
                }
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    fail("BLE write failed with status " + status + "; full-frame retry required");
                    return;
                }
                if (isDataWrite && dataWriteWithResponse && streaming) {
                    handler.removeCallbacks(dataPump);
                    pumpData();
                }
            });
        }
    };

    private void beginServiceDiscovery(BluetoothGatt callbackGatt, int mtu) {
        if (serviceDiscoveryStarted || resultWritten) {
            return;
        }
        serviceDiscoveryStarted = true;
        if (mtuFallback != null) {
            handler.removeCallbacks(mtuFallback);
        }
        log("Using GATT MTU " + mtu + "; discovering services");
        if (!callbackGatt.discoverServices()) {
            fail("Android refused service discovery");
        }
    }

    private void prepareImageService() {
        BluetoothGattService service = gatt.getService(SERVICE_FEF0);
        if (service == null) {
            service = gatt.getService(SERVICE_FDF0);
        }
        if (service == null) {
            fail("TodooCard image service FEF0/FDF0 is missing");
            return;
        }
        controlCharacteristic = service.getCharacteristic(CONTROL_FEF1);
        if (controlCharacteristic == null) {
            controlCharacteristic = service.getCharacteristic(CONTROL_FDF1);
        }
        dataCharacteristic = service.getCharacteristic(DATA_FEF2);
        if (dataCharacteristic == null) {
            dataCharacteristic = service.getCharacteristic(DATA_FDF2);
        }
        if (controlCharacteristic == null || dataCharacteristic == null) {
            fail("TodooCard FEF1/FEF2 characteristics are missing");
            return;
        }
        if ("probe".equals(mode)) {
            JSONObject extra = new JSONObject();
            try {
                extra.put("device_id", targetAddress);
                extra.put("device_name", targetDevice.getName() == null ? "" : targetDevice.getName());
                extra.put("secure", advertisement.secure);
                extra.put("firmware", advertisement.firmware >= 0
                        ? String.format(Locale.ROOT, "0x%02X", advertisement.firmware)
                        : "not-advertised");
                extra.put("connection", directBondedConnection
                        ? "android-bond" : "verified-advertisement");
                extra.put("block_size", 240);
                extra.put("mtu", negotiatedMtu);
            } catch (JSONException | SecurityException ignored) {
            }
            succeed("Exact address, advertisement, encrypted bond, and FEF1/FEF2 access verified", extra);
            return;
        }
        if (!gatt.setCharacteristicNotification(controlCharacteristic, true)) {
            fail("Android refused control notifications");
            return;
        }
        BluetoothGattDescriptor descriptor = controlCharacteristic.getDescriptor(CLIENT_CONFIG);
        if (descriptor == null) {
            fail("Control notification descriptor is missing");
            return;
        }
        descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
        if (!gatt.writeDescriptor(descriptor)) {
            fail("Android refused the notification descriptor write");
        }
    }

    private void beginTransfer() {
        if (!notificationsReady || transferStarted) {
            return;
        }
        transferStarted = true;
        handler.removeCallbacks(operationTimeout);
        writeControl(new byte[]{0x01});
    }

    private void writeControl(byte[] bytes) {
        controlCharacteristic.setWriteType(
                (controlCharacteristic.getProperties() & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0
                        ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                        : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
        controlCharacteristic.setValue(bytes);
        log("Control -> " + hex(bytes));
        if (!gatt.writeCharacteristic(controlCharacteristic)) {
            fail("Android rejected the control write");
            return;
        }
        if (controlTimeout != null) {
            handler.removeCallbacks(controlTimeout);
        }
        controlTimeout = () -> fail("Timed out waiting for TodooCard control response");
        handler.postDelayed(controlTimeout, 5_000);
    }

    private void handleControl(byte[] bytes) {
        if (bytes == null || bytes.length < 2) {
            return;
        }
        if (controlTimeout != null) {
            handler.removeCallbacks(controlTimeout);
        }
        log("Control <- " + hex(bytes));
        int command = bytes[0] & 0xff;
        int status = bytes[1] & 0xff;
        if (command == 0x01) {
            if (bytes.length < 3 || (bytes[2] & 0xff) != 0) {
                fail("TodooCard rejected the block-size request");
                return;
            }
            blockPayloadSize = (bytes[1] & 0xff) - 4;
            if (blockPayloadSize <= 0 || blockPayloadSize > 240) {
                fail("Unsafe block payload size: " + blockPayloadSize);
                return;
            }
            int requiredMtu = blockPayloadSize + 7;
            if (negotiatedMtu < requiredMtu) {
                fail("Negotiated GATT MTU " + negotiatedMtu
                        + " is too small for the required data packet; need " + requiredMtu);
                return;
            }
            byte[] announce = new byte[6];
            announce[0] = 0x02;
            putLittleEndian(announce, 1, payload.length);
            announce[5] = 0x01;
            writeControl(announce);
        } else if (command == 0x02) {
            if (status != 0) {
                fail("TodooCard rejected the payload length");
                return;
            }
            writeControl(new byte[]{0x03});
        } else if (command == 0x05) {
            if (status == 0x08) {
                if (finalAckTimeout != null) {
                    handler.removeCallbacks(finalAckTimeout);
                }
                succeed("Transfer completed and refresh acknowledged", transferMetrics());
                return;
            }
            if (status != 0 || bytes.length < 6) {
                fail("TodooCard rejected a data block");
                return;
            }
            int requestedStart = littleEndian(bytes, 2);
            if (requestedStart != 0) {
                fail("TodooCard requested a non-zero start block; refusing a mid-frame resume");
                return;
            }
            if (!streaming) {
                nextBlock = 0;
                streaming = true;
                int properties = dataCharacteristic.getProperties();
                boolean supportsWriteWithoutResponse =
                        (properties & BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0;
                boolean supportsWriteWithResponse =
                        (properties & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0;
                if (!supportsWriteWithoutResponse && !supportsWriteWithResponse) {
                    fail("TodooCard data characteristic is not writable");
                    return;
                }
                dataWriteWithResponse = supportsWriteWithResponse;
                transferStartedAt = SystemClock.elapsedRealtime();
                log("Starting full-frame stream at block " + nextBlock + " using " + (dataWriteWithResponse ? "write-with-response" : "paced write-without-response"));
                postProgress(0, -1);
                pumpData();
            }
        }
    }

    private void pumpData() {
        if (!streaming || resultWritten) {
            return;
        }
        int offset = nextBlock * blockPayloadSize;
        if (offset >= payload.length) {
            waitForFinalAck();
            return;
        }
        int length = Math.min(blockPayloadSize, payload.length - offset);
        byte[] packet = new byte[length + 4];
        putLittleEndian(packet, 0, nextBlock);
        System.arraycopy(payload, offset, packet, 4, length);
        dataCharacteristic.setWriteType(dataWriteWithResponse
                ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
        dataCharacteristic.setValue(packet);
        if (!gatt.writeCharacteristic(dataCharacteristic)) {
            long now = SystemClock.elapsedRealtime();
            if (queueBusySince == 0) {
                queueBusySince = now;
            } else if (now - queueBusySince >= QUEUE_BUSY_TIMEOUT_MS) {
                fail("Android BLE queue remained busy; full-frame retry required");
                return;
            }
            handler.postDelayed(dataPump, QUEUE_RETRY_MS);
            return;
        }
        queueBusySince = 0;
        nextBlock++;
        if (dataWriteWithResponse) {
            if (dataWriteTimeout != null) {
                handler.removeCallbacks(dataWriteTimeout);
            }
            int pendingBlock = nextBlock - 1;
            dataWriteTimeout = () -> fail(
                    "Timed out waiting for GATT confirmation of block " + pendingBlock
                            + "; full-frame retry required");
            handler.postDelayed(dataWriteTimeout, 10_000);
        }
        int percent = (int) Math.floor(100.0 * Math.min(payload.length, offset + length) / payload.length);
        if (percent != lastProgress && (percent % 5 == 0 || percent == 100)) {
            lastProgress = percent;
            log("Progress " + percent + "% block=" + (nextBlock - 1));
            postProgress(percent, nextBlock - 1);
        }
        if (!dataWriteWithResponse && offset + length >= payload.length) {
            waitForFinalAck();
            return;
        }
        if (!dataWriteWithResponse) {
            handler.postDelayed(dataPump, NO_RESPONSE_PACE_MS);
        }
    }

    private void waitForFinalAck() {
        if (payloadWrittenAt == 0) {
            payloadWrittenAt = SystemClock.elapsedRealtime();
        }
        streaming = false;
        log("Payload written; waiting for final refresh acknowledgement");
        finalAckTimeout = () -> fail("Timed out waiting for final refresh acknowledgement");
        handler.postDelayed(finalAckTimeout, 180_000);
    }

    private JSONObject transferMetrics() {
        JSONObject metrics = new JSONObject();
        long completedAt = SystemClock.elapsedRealtime();
        long writeMs = payloadWrittenAt > transferStartedAt
                ? payloadWrittenAt - transferStartedAt : 0;
        try {
            metrics.put("blocks", nextBlock);
            metrics.put("mtu", negotiatedMtu);
            metrics.put("write_mode", dataWriteWithResponse
                    ? "with-response" : "without-response");
            metrics.put("connection", directBondedConnection
                    ? "android-bond" : "verified-advertisement");
            metrics.put("payload_write_ms", writeMs);
            metrics.put("refresh_wait_ms", payloadWrittenAt > 0
                    ? completedAt - payloadWrittenAt : 0);
            metrics.put("transfer_ms", transferStartedAt > 0
                    ? completedAt - transferStartedAt : 0);
            if (writeMs > 0) {
                metrics.put("throughput_kib_s",
                        payload.length * 1000.0 / writeMs / 1024.0);
            }
        } catch (JSONException ignored) {
        }
        return metrics;
    }

    private void postProgress(int percent, int block) {
        JSONObject progress = new JSONObject();
        try {
            progress.put("request_id", requestId);
            progress.put("mode", mode);
            progress.put("percent", percent);
            progress.put("block", block);
            byte[] body = progress.toString().getBytes(StandardCharsets.UTF_8);
            new Thread(() -> postProgressBody(body),
                    "todoocard-progress-" + percent).start();
        } catch (JSONException error) {
            Log.w(TAG, "Cannot create progress heartbeat", error);
        }
    }

    private void postProgressBody(byte[] body) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(callbackBaseUrl + "/progress").openConnection();
            connection.setConnectTimeout(3_000);
            connection.setReadTimeout(3_000);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(body.length);
            connection.setDoOutput(true);
            try (OutputStream stream = connection.getOutputStream()) {
                stream.write(body);
            }
            if (connection.getResponseCode() != 200) {
                Log.w(TAG, "Progress heartbeat returned HTTP " + connection.getResponseCode());
            }
        } catch (IOException error) {
            Log.w(TAG, "Cannot return transfer progress to Minis", error);
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private void finishList() {
        stopScan();
        JSONArray devices = new JSONArray();
        for (JSONObject item : listedDevices.values()) {
            devices.put(item);
        }
        JSONObject extra = new JSONObject();
        try {
            extra.put("devices", devices);
        } catch (JSONException ignored) {
        }
        succeed("Scan completed: " + devices.length() + " compatible device(s)", extra);
    }

    private void succeed(String message, JSONObject extra) {
        writeResult(true, message, extra);
        log(message);
        cleanupBluetooth();
        cleanupLocation();
    }

    private void fail(String message) {
        if (resultWritten) {
            return;
        }
        writeResult(false, message, null);
        log("FAILED: " + message);
        cleanupBluetooth();
        cleanupLocation();
    }

    private synchronized void writeResult(boolean ok, String message, JSONObject extra) {
        if (resultWritten) {
            return;
        }
        resultWritten = true;
        JSONObject result = new JSONObject();
        try {
            result.put("request_id", requestId);
            result.put("ok", ok);
            result.put("mode", mode);
            result.put("message", message);
            if (extra != null) {
                java.util.Iterator<String> keys = extra.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    result.put(key, extra.get(key));
                }
            }
            byte[] body = result.toString().getBytes(StandardCharsets.UTF_8);
            new Thread(() -> postResult(body), "todoocard-result").start();
        } catch (JSONException error) {
            Log.e(TAG, "Cannot create result", error);
            BridgeForegroundService.stop(this);
        }
    }

    private byte[] httpGet(String suffix, int maximumBytes) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(callbackBaseUrl + "/" + suffix).openConnection();
        connection.setConnectTimeout(5_000);
        connection.setReadTimeout(30_000);
        connection.setUseCaches(false);
        connection.setRequestMethod("GET");
        try {
            if (connection.getResponseCode() != 200) {
                throw new IOException("local callback returned HTTP " + connection.getResponseCode());
            }
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int total = 0;
                int read;
                while ((read = input.read(buffer)) != -1) {
                    total += read;
                    if (total > maximumBytes) {
                        throw new IOException("local response exceeded the safety limit");
                    }
                    output.write(buffer, 0, read);
                }
                return output.toByteArray();
            }
        } finally {
            connection.disconnect();
        }
    }

    private void postResult(byte[] body) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(callbackBaseUrl + "/result").openConnection();
            connection.setConnectTimeout(5_000);
            connection.setReadTimeout(10_000);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(body.length);
            connection.setDoOutput(true);
            try (OutputStream stream = connection.getOutputStream()) {
                stream.write(body);
            }
            if (connection.getResponseCode() != 200) {
                throw new IOException("local result callback returned HTTP " + connection.getResponseCode());
            }
            handler.post(() -> log("Result returned to Minis"));
        } catch (IOException error) {
            Log.e(TAG, "Cannot return result to Minis", error);
            handler.post(() -> log("FAILED: Could not return the result to Minis"));
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
            handler.post(() -> {
                BridgeForegroundService.stop(this);
                finishAndRemoveTask();
            });
        }
    }

    private void cleanupBluetooth() {
        stopScan();
        if (gatt != null) {
            try {
                gatt.disconnect();
                gatt.close();
            } catch (SecurityException ignored) {
            }
            gatt = null;
        }
    }

    private void cleanupLocation() {
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(locationListener);
            } catch (SecurityException ignored) {
            }
            locationManager = null;
        }
    }

    private void stopScan() {
        if (scanner != null && hasPermissions()) {
            try {
                scanner.stopScan(scanCallback);
            } catch (SecurityException ignored) {
            }
        }
        scanner = null;
    }

    private void log(String message) {
        Log.i(TAG, message);
        output.append(message + "\n");
    }

    private static String hex(byte[] bytes) {
        StringBuilder output = new StringBuilder();
        for (byte value : bytes) {
            if (output.length() > 0) {
                output.append(' ');
            }
            output.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        }
        return output.toString();
    }

    private static void putLittleEndian(byte[] output, int offset, int value) {
        output[offset] = (byte) (value & 0xff);
        output[offset + 1] = (byte) ((value >> 8) & 0xff);
        output[offset + 2] = (byte) ((value >> 16) & 0xff);
        output[offset + 3] = (byte) ((value >> 24) & 0xff);
    }

    private static int littleEndian(byte[] bytes, int offset) {
        return (bytes[offset] & 0xff)
                | ((bytes[offset + 1] & 0xff) << 8)
                | ((bytes[offset + 2] & 0xff) << 16)
                | ((bytes[offset + 3] & 0xff) << 24);
    }

    private static void validatePayload(byte[] bytes) {
        int rawLength = WIDTH * HEIGHT / 2;
        int expectedLength = 4 + (rawLength / 64) * 67;
        if (bytes.length != expectedLength || bytes[0] != 0 || bytes[1] != 0 || bytes[2] != 0 || bytes[3] != 0) {
            throw new IllegalArgumentException("payload size or prefix is invalid");
        }
        for (int offset = 4; offset < bytes.length; offset += 67) {
            if (bytes[offset] != 0x74 || bytes[offset + 1] != 0x43 || bytes[offset + 2] != 0x40) {
                throw new IllegalArgumentException("QuickLZ stored-frame marker is invalid at offset " + offset);
            }
        }
    }

    private static final class Advertisement {
        final int screenType;
        final int firmware;
        final boolean secure;
        final boolean pairingOpen;

        Advertisement(int screenType, int firmware, boolean secure, boolean pairingOpen) {
            this.screenType = screenType;
            this.firmware = firmware;
            this.secure = secure;
            this.pairingOpen = pairingOpen;
        }
    }
}
