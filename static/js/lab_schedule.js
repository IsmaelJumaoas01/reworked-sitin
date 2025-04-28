// Debug logging function
function debugLog(message, data = null) {
    const timestamp = new Date().toISOString();
    if (data) {
        console.log(`[${timestamp}] ${message}:`, data);
    } else {
        console.log(`[${timestamp}] ${message}`);
    }
}

// Function to show step 1
function showStep1() {
    document.getElementById('step1').style.display = 'block';
    document.getElementById('step2').style.display = 'none';
}

// Function to show step 2
function showStep2() {
    document.getElementById('step1').style.display = 'none';
    document.getElementById('step2').style.display = 'block';
}

// Function to handle lab and day selection
function handleLabDaySelection() {
    const labId = document.getElementById('lab').value;
    const day = document.getElementById('day').value;
    
    debugLog('Lab and Day selected:', { labId, day });
    
    if (!labId || !day) {
        alert('Please select both laboratory and day');
        return;
    }
    
    // Store selected values
    document.getElementById('selectedLab').value = labId;
    document.getElementById('selectedDay').value = day;
    
    // Get available time slots
    getAvailableTimeSlots(labId, day);
    
    // Show step 2
    showStep2();
}

// Function to get available time slots
function getAvailableTimeSlots(labId, day) {
    debugLog('Getting available time slots for:', { labId, day });
    
    if (!labId || !day) {
        debugLog('Missing required parameters');
        return;
    }
    
    debugLog('Fetching available slots from server...');
    fetch(`/admin/lab-schedules/available-slots?lab_id=${labId}&day_of_week=${day}`)
        .then(response => {
            debugLog('Server response status:', response.status);
            return response.json();
        })
        .then(data => {
            debugLog('Available time slots response:', data);
            
            const container = document.getElementById('timeSlotsContainer');
            container.innerHTML = '';
            
            if (data.success && data.available_slots && data.available_slots.length > 0) {
                debugLog('Found available slots:', data.available_slots.length);
                
                // Group slots by duration
                const slotsByDuration = {
                    '1': [],
                    '1.5': [],
                    '2': []
                };
                
                data.available_slots.forEach(slot => {
                    const duration = slot.DURATION;
                    if (duration === 1) {
                        slotsByDuration['1'].push(slot);
                    } else if (duration === 1.5) {
                        slotsByDuration['1.5'].push(slot);
                    } else if (duration === 2) {
                        slotsByDuration['2'].push(slot);
                    }
                });
                
                // Create sections for each duration
                Object.entries(slotsByDuration).forEach(([duration, slots]) => {
                    if (slots.length > 0) {
                        const section = document.createElement('div');
                        section.className = 'col-12 mb-4';
                        section.innerHTML = `
                            <h6 class="mb-3">${duration}-Hour Slots</h6>
                            <div class="row" id="slots-${duration}"></div>
                        `;
                        container.appendChild(section);
                        
                        const slotsContainer = document.getElementById(`slots-${duration}`);
                        slots.forEach(slot => {
                            const col = document.createElement('div');
                            col.className = 'col-md-4 mb-3';
                            
                            const card = document.createElement('div');
                            card.className = 'card time-slot-card';
                            card.style.cursor = 'pointer';
                            
                            // Format the time for display
                            const startTime = new Date(`2000-01-01T${slot.START_TIME}`).toLocaleTimeString('en-US', { 
                                hour: 'numeric', 
                                minute: '2-digit', 
                                hour12: true 
                            });
                            const endTime = new Date(`2000-01-01T${slot.END_TIME}`).toLocaleTimeString('en-US', { 
                                hour: 'numeric', 
                                minute: '2-digit', 
                                hour12: true 
                            });
                            
                            card.innerHTML = `
                                <div class="card-body text-center">
                                    <h5 class="card-title">${startTime} - ${endTime}</h5>
                                    <small class="text-muted">${duration} hour${duration > 1 ? 's' : ''}</small>
                                    <input type="radio" name="time_slot" value="${slot.START_TIME},${slot.END_TIME}" class="d-none">
                                </div>
                            `;
                            
                            card.addEventListener('click', function() {
                                // Remove active class from all cards
                                document.querySelectorAll('.time-slot-card').forEach(c => {
                                    c.classList.remove('active');
                                });
                                // Add active class to clicked card
                                this.classList.add('active');
                                // Check the radio button
                                this.querySelector('input[type="radio"]').checked = true;
                            });
                            
                            col.appendChild(card);
                            slotsContainer.appendChild(col);
                        });
                    }
                });
            } else {
                container.innerHTML = '<div class="col-12"><div class="alert alert-warning">No available time slots found</div></div>';
            }
        })
        .catch(error => {
            console.error('Error fetching available time slots:', error);
            document.getElementById('timeSlotsContainer').innerHTML = 
                '<div class="col-12"><div class="alert alert-danger">Error loading time slots</div></div>';
            debugLog('Error occurred while fetching time slots:', error);
        });
}

// Schedule form submission
document.addEventListener('DOMContentLoaded', function() {
    const scheduleForm = document.getElementById('scheduleForm');
    if (scheduleForm) {
        scheduleForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = {
                lab_id: document.getElementById('selectedLab').value,
                purpose_id: document.getElementById('purpose').value,
                day_of_week: document.getElementById('selectedDay').value,
                time_slot: document.querySelector('input[name="time_slot"]:checked')?.value,
                status: document.getElementById('status').value
            };
            
            debugLog('Form submission attempt:', formData);
            
            if (!formData.time_slot) {
                alert('Please select a time slot');
                debugLog('Form submission failed: No time slot selected');
                return;
            }
            
            const [start_time, end_time] = formData.time_slot.split(',');
            formData.start_time = start_time;
            formData.end_time = end_time;
            
            debugLog('Submitting schedule:', formData);
            
            fetch('/admin/lab-schedules/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            })
            .then(response => {
                debugLog('Server response status:', response.status);
                return response.json();
            })
            .then(data => {
                debugLog('Server response:', data);
                if (data.success) {
                    alert('Schedule added successfully');
                    window.location.href = '/admin/lab-schedules';
                } else {
                    alert(data.message || 'Error adding schedule');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                debugLog('Error submitting form:', error);
                alert('Error adding schedule');
            });
        });
    }
}); 