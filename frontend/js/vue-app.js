const { createApp, ref, computed, nextTick, watch } = Vue;

document.addEventListener('DOMContentLoaded', () => {
    createApp({
        setup() {
            const API_BASE_URL = 'http://localhost:8000';
            const STATUS_MESSAGES = {
                WAITING: 'Waiting for user input',
                PROCESSING: 'Processing your request...',
                COMPLETED: 'Processing completed',
                ERROR: 'Error occurred, please try again',
                TIMEOUT: 'Processing timeout, interrupted',
                SESSION_ERROR: 'Session validation failed, please refresh the page',
                SESSION_INIT_ERROR: 'Session initialization failed, please refresh the page'
            };
            
            const query = ref('');
            const recursionLimit = ref(150);
            const isLoading = ref(false);
            const processContent = ref(null);
            const statusMessage = ref(STATUS_MESSAGES.WAITING);
            const resultFiles = ref([]);
            const selectedFileIndex = ref(null);
            const sessionId = ref('');
            const workspaceFiles = ref([]);
            const selectedWorkspaceFileIndex = ref(null);
            
            // Chat related variables
            const userQuery = ref('');
            const userQueryTime = ref('');
            const chatMessages = ref([]);
            
            const hasResponse = computed(() => chatMessages.value.length > 0 || userQuery.value);
            const hasResult = computed(() => resultFiles.value.length > 0);
            const selectedFile = computed(() => {
                if (selectedFileIndex.value !== null && resultFiles.value.length > selectedFileIndex.value) {
                    return resultFiles.value[selectedFileIndex.value];
                }
                return null;
            });
            const selectedWorkspaceFile = computed(() => {
                if (selectedWorkspaceFileIndex.value !== null && workspaceFiles.value.length > selectedWorkspaceFileIndex.value) {
                    return workspaceFiles.value[selectedWorkspaceFileIndex.value];
                }
                return null;
            });
            
            // Get formatted current time string
            function getCurrentTime() {
                const now = new Date();
                const hours = now.getHours().toString().padStart(2, '0');
                const minutes = now.getMinutes().toString().padStart(2, '0');
                return `${hours}:${minutes}`;
            }
            
            // Select file
            function selectFile(index) {
                selectedFileIndex.value = index;
            }
            
            // Download result file
            function downloadResult() {
                if (!selectedFile.value) return;
                
                const blob = new Blob([selectedFile.value.content], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = selectedFile.value.name;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
            
            // Auto scroll to bottom
            watch(chatMessages, () => {
                nextTick(() => {
                    if (processContent.value) {
                        processContent.value.scrollTop = processContent.value.scrollHeight;
                    }
                });
            }, { deep: true });
            
            // Session management related functions
            // Validate if session ID is valid
            async function validateSession() {
                if (!sessionId.value) return false;
                
                try {
                    console.log('Validating session ID:', sessionId.value);
                    const checkResponse = await fetch(`${API_BASE_URL}/files?session_id=${sessionId.value}`);
                    
                    if (!checkResponse.ok) {
                        console.log('Session ID invalid');
                        return false;
                    }
                    
                    // Session valid, get session ID from response header
                    updateSessionIdFromHeader(checkResponse);
                    return true;
                } catch (error) {
                    console.error('Error validating session ID:', error);
                    return false;
                }
            }
            
            // Update session ID from response header
            function updateSessionIdFromHeader(response) {
                const headerSessionId = response.headers.get('X-Session-ID');
                if (headerSessionId && headerSessionId !== sessionId.value) {
                    console.log(`Updating session ID from response header: ${sessionId.value} -> ${headerSessionId}`);
                    sessionId.value = headerSessionId;
                    return true;
                }
                return false;
            }
            
            // Create new session
            async function createNewSession() {
                try {
                    console.log('Creating new session');
                    const sessionResponse = await fetch(`${API_BASE_URL}/session`, {
                        method: 'POST'
                    });
                    
                    if (!sessionResponse.ok) {
                        console.error('Failed to create new session');
                        return false;
                    }
                    
                    // Get session ID from response header
                    if (updateSessionIdFromHeader(sessionResponse)) {
                        return true;
                    }
                    
                    // If no session ID in response header, get from response body (as fallback)
                    try {
                        const data = await sessionResponse.json();
                        if (data.session_id) {
                            console.log(`Getting session ID from response body: ${data.session_id}`);
                            sessionId.value = data.session_id;
                            return true;
                        }
                    } catch (e) {
                        console.error('Failed to parse session response:', e);
                    }
                    
                    return false;
                } catch (error) {
                    console.error('Error creating new session:', error);
                    return false;
                }
            }
            
            // Ensure valid session, create new one if invalid
            async function ensureValidSession() {
                // If no session ID or session ID invalid, create new session
                if (!await validateSession()) {
                    return await createNewSession();
                }
                return true;
            }
            
            // Handle session error
            function handleSessionError(errorType) {
                isLoading.value = false;
                statusMessage.value = STATUS_MESSAGES.SESSION_ERROR;
                chatMessages.value.push({
                    'team': 'system',
                    'sender': 'System',
                    'content': errorType === 'validation' 
                        ? 'Error validating session ID. Please ensure the backend server is running and the address is configured correctly.'
                        : 'Error creating new session. Please ensure the backend server is running and the address is configured correctly.',
                    'timestamp': getCurrentTime()
                });
                return false;
            }
            
            // Select workspace file
            function selectWorkspaceFile(index) {
                selectedWorkspaceFileIndex.value = index;
            }
            
            // Refresh workspace file list
            async function refreshWorkspaceFiles() {
                if (!sessionId.value) return;
                
                try {
                    const response = await fetch(`${API_BASE_URL}/files?session_id=${sessionId.value}`);
                    
                    if (!response.ok) {
                        throw new Error(`Failed to get file list: ${response.status}`);
                    }
                    
                    // Get session ID from response header
                    updateSessionIdFromHeader(response);
                    
                    const data = await response.json();
                    workspaceFiles.value = data.files;
                    
                    // If there are files but none selected, select the first one
                    if (workspaceFiles.value.length > 0 && selectedWorkspaceFileIndex.value === null) {
                        selectedWorkspaceFileIndex.value = 0;
                    }
                } catch (error) {
                    console.error('Failed to get workspace file list:', error);
                    // Can display error message on UI
                }
            }
            
            // Download workspace file
            async function downloadWorkspaceFile() {
                if (!selectedWorkspaceFile.value || !sessionId.value) return;
                
                const fileUrl = `${API_BASE_URL}/download?session_id=${sessionId.value}&file_path=${encodeURIComponent(selectedWorkspaceFile.value)}`;
                
                try {
                    // First validate if session is valid
                    if (!await validateSession()) {
                        // Session invalid, try to refresh
                        if (!await createNewSession()) {
                            alert('Session expired and cannot be recreated. Please refresh the page and try again.');
                            return;
                        }
                        
                        // Refresh workspace file list
                        await refreshWorkspaceFiles();
                        
                        // Show notification
                        alert('Session has been refreshed, please try downloading again.');
                        return;
                    }
                    
                    // Check if file is in the list
                    if (!workspaceFiles.value.includes(selectedWorkspaceFile.value)) {
                        alert('File does not exist or has been deleted');
                        return;
                    }
                    
                    // File exists, trigger download
                    const a = document.createElement('a');
                    a.href = fileUrl;
                    a.download = selectedWorkspaceFile.value.split('/').pop(); // Use filename as download name
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                } catch (error) {
                    console.error('Error downloading file:', error);
                    alert('Error downloading file, please try again');
                }
            }
            
            // Initialize function - create session on page load
            async function initializeSession() {
                try {
                    // Validate existing session or create new session
                    if (await ensureValidSession()) {
                        // Get workspace file list
                        await refreshWorkspaceFiles();
                    } else {
                        // Show initialization failed error
                        statusMessage.value = STATUS_MESSAGES.SESSION_INIT_ERROR;
                        chatMessages.value.push({
                            'team': 'system',
                            'sender': 'System',
                            'content': 'Failed to connect to backend API. Please ensure the backend server is running and the address is configured correctly.',
                            'timestamp': getCurrentTime()
                        });
                    }
                } catch (error) {
                    console.error('Failed to initialize session:', error);
                    statusMessage.value = STATUS_MESSAGES.SESSION_INIT_ERROR;
                    chatMessages.value.push({
                        'team': 'system',
                        'sender': 'System',
                        'content': 'Failed to connect to backend API. Please ensure the backend server is running and the address is configured correctly.',
                        'timestamp': getCurrentTime()
                    });
                }
            }
            
            // Call initialization function on page load
            initializeSession();
            
            // Submit query
            async function submitQuery() {
                if (!query.value.trim()) return;
                
                // Clear previous chat messages
                chatMessages.value = [];
                
                // Record user query
                userQuery.value = query.value;
                userQueryTime.value = getCurrentTime();
                
                isLoading.value = true;
                statusMessage.value = STATUS_MESSAGES.PROCESSING;
                resultFiles.value = [];
                selectedFileIndex.value = null;
                
                // Ensure valid session
                if (!await ensureValidSession()) {
                    return handleSessionError('session');
                }
                
                // Only clear if no workspace file list
                if (workspaceFiles.value.length === 0) {
                    selectedWorkspaceFileIndex.value = null;
                }
                
                // Use EventSource to receive streaming response
                const eventSource = new EventSource(
                    `${API_BASE_URL}/query?query=${encodeURIComponent(query.value)}&recursion_limit=${recursionLimit.value}${sessionId.value ? `&session_id=${sessionId.value}` : ''}`
                );
                
                // Add open event handler
                eventSource.onopen = (event) => {
                    console.log('EventSource connection opened');
                    
                    // Since EventSource cannot directly access response headers, we use a separate request to get the latest session ID
                    fetch(`${API_BASE_URL}/session${sessionId.value ? `?session_id=${sessionId.value}` : ''}`, {
                        method: 'GET'
                    })
                    .then(response => {
                        // Get session ID from response header
                        updateSessionIdFromHeader(response);
                        return response.json();
                    })
                    .catch(error => {
                        console.error('Failed to get session info:', error);
                    });
                };
                
                eventSource.onmessage = (event) => {
                    try {
                        // Parse JSON data
                        const parsedData = JSON.parse(event.data);
                        const response = parsedData.response;
                        const metadata = parsedData.metadata;
                        const sender_id = metadata.checkpoint_ns;
                        const sender_name = sender_id.split(':')[0];
                        const teamName = sender_name.split('_team')[0];
                        // let content;
                        
                        // if (parsedData.messages) {
                        //     content = parsedData.messages;
                        // } else if (parsedData.next) {
                        //     content = parsedData.next === "__end__" ? "End" : "Passing to " + parsedData.next;
                        // } else {
                        //     content = parsedData;
                        // }
                        
                        // let teamName = parsedData.sender;
                        // if (teamName && teamName.endsWith('_team')) {
                        //     teamName = teamName.split('_team')[0];
                        // }
                        
                        // chatMessages.value.push({
                        //     'team': teamName,
                        //     'sender': parsedData.sender,
                        //     'content': content,
                        //     'timestamp': getCurrentTime()
                        // });
                        if (chatMessages.value.length > 0) {
                            const lastIndex = chatMessages.value.length - 1;
                            if (chatMessages.value[lastIndex].sender_id === sender_id) {
                                chatMessages.value[lastIndex].content += response;
                                chatMessages.value[lastIndex].timestamp = getCurrentTime();
                            } else {
                                chatMessages.value.push({
                                    'team': teamName,
                                    'sender': sender_name,
                                    'sender_id': sender_id,
                                    'content': response,
                                    'timestamp': getCurrentTime()
                                })
                            }
                        } else {
                            chatMessages.value.push({
                                'team': teamName,
                                'sender': sender_name,
                                'sender_id': sender_id,
                                'content': response,
                                'timestamp': getCurrentTime()
                            })
                        }
                    } catch (error) {
                        chatMessages.value.push({
                            'team': 'system',
                            'sender': 'System',
                            'content': error.message,
                            'timestamp': getCurrentTime()
                        });
                    }

                };
                
                eventSource.onerror = (error) => {
                    console.error('EventSource error:', error);
                    eventSource.close();
                    isLoading.value = false;
                    statusMessage.value = STATUS_MESSAGES.ERROR;
                    
                    // If connection error, show notification
                    if (chatMessages.value.length === 0) {
                        chatMessages.value.push({
                            'team': 'system',
                            'sender': 'System',
                            'content': 'Failed to connect to backend API. Please ensure the backend server is running and the address is configured correctly.',
                            'timestamp': getCurrentTime()
                        });
                    }
                };
                
                // When stream ends
                eventSource.addEventListener('end', () => {
                    eventSource.close();
                    isLoading.value = false;
                    statusMessage.value = STATUS_MESSAGES.COMPLETED;
                    // Refresh workspace file list after completion
                    refreshWorkspaceFiles();
                });
                
                // Fallback: close connection if still open after 5 minutes
                setTimeout(() => {
                    if (eventSource.readyState !== 2) {
                        eventSource.close();
                        isLoading.value = false;
                        statusMessage.value = STATUS_MESSAGES.TIMEOUT;
                        chatMessages.value.push({
                            'team': 'system',
                            'sender': 'System',
                            'content': '\n\n[System] Response timeout, connection closed.',
                            'timestamp': getCurrentTime()
                        });
                    }
                }, 5 * 60 * 1000);
            }
            
            // Clear response
            function clearResponse() {
                chatMessages.value = [];
                userQuery.value = '';
                resultFiles.value = [];
                selectedFileIndex.value = null;
                statusMessage.value = STATUS_MESSAGES.WAITING;
            }
            
            return {
                query,
                recursionLimit,
                isLoading,
                hasResponse,
                hasResult,
                processContent,
                statusMessage,
                resultFiles,
                selectedFileIndex,
                selectedFile,
                sessionId,
                workspaceFiles,
                selectedWorkspaceFileIndex,
                selectedWorkspaceFile,
                userQuery,
                userQueryTime,
                chatMessages,
                submitQuery,
                clearResponse,
                selectFile,
                downloadResult,
                selectWorkspaceFile,
                refreshWorkspaceFiles,
                downloadWorkspaceFile,
                ensureValidSession
            };
        }
    }).mount('#app');
});