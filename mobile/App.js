import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  FlatList,
  ScrollView,
  ActivityIndicator,
  Alert,
  Modal,
  SafeAreaView,
  StatusBar,
  RefreshControl,
  Switch
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

// Default PC Backend URL (User's local network IP)
const DEFAULT_SERVER_URL = 'http://192.168.156.89:8000';

export default function App() {
  const [serverUrl, setServerUrl] = useState(DEFAULT_SERVER_URL);
  const [tempServerUrl, setTempServerUrl] = useState(DEFAULT_SERVER_URL);
  const [isSettingsVisible, setIsSettingsVisible] = useState(false);
  const [isOnline, setIsOnline] = useState(false);
  const [activeTab, setActiveTab] = useState('search'); // 'search', 'jobs', 'history'

  // Search Filters
  const [keywords, setKeywords] = useState('Desarrollador Python');
  const [location, setLocation] = useState('Alicante');
  const [salaryMin, setSalaryMin] = useState('20000');
  const [modality, setModality] = useState('Todas'); // 'Todas', 'En remoto', 'Presencial', 'Híbrido'
  const [allowUnspecifiedSalary, setAllowUnspecifiedSalary] = useState(true);
  const [maxResults, setMaxResults] = useState('10');

  // App Data State
  const [searching, setSearching] = useState(false);
  const [applyingUrl, setApplyingUrl] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Check Backend Health Status
  const checkHealth = async (url = serverUrl) => {
    try {
      const response = await fetch(`${url}/health`, { method: 'GET' });
      if (response.ok) {
        setIsOnline(true);
        return true;
      } else {
        setIsOnline(false);
        return false;
      }
    } catch (error) {
      setIsOnline(false);
      return false;
    }
  };

  useEffect(() => {
    checkHealth();
  }, [serverUrl]);

  // Execute Job Search
  const handleSearchJobs = async () => {
    if (!keywords.trim()) {
      Alert.alert('Campo requerido', 'Por favor ingresa palabras clave de búsqueda.');
      return;
    }

    setSearching(true);
    try {
      const payload = {
        keywords: keywords.trim(),
        location: location.trim() || undefined,
        salary_min: parseInt(salaryMin, 10) || 0,
        modality: modality,
        allow_unspecified_salary: allowUnspecifiedSalary,
        max_results: parseInt(maxResults, 10) || 10
      };

      const response = await fetch(`${serverUrl}/search-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const json = await response.json();

      if (response.ok && json.status === 'success') {
        setJobs(json.data || []);
        setActiveTab('jobs');
        Alert.alert('Búsqueda completada', `Se encontraron ${json.count} ofertas coincidentes.`);
      } else {
        Alert.alert('Error en búsqueda', json.detail || 'No se pudieron recuperar las ofertas.');
      }
    } catch (error) {
      Alert.alert('Error de conexión', `No se pudo conectar con el servidor (${serverUrl}). Verifica que main.py esté en ejecución.`);
    } finally {
      setSearching(false);
    }
  };

  // Apply to a Specific Job
  const handleApplyToJob = async (job) => {
    Alert.alert(
      'Confirmar Postulación',
      `¿Deseas postularte automáticamente a:\n"${job.title}" en ${job.company}?`,
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Sí, Postular',
          onPress: async () => {
            setApplyingUrl(job.url);
            try {
              const payload = {
                job_url: job.url,
                killer_answers: []
              };

              const response = await fetch(`${serverUrl}/apply-job`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
              });

              const json = await response.json();

              if (response.ok && json.status === 'success') {
                Alert.alert('🎉 ¡Postulación Exitosa!', json.message || 'Te has inscrito en la oferta correctamente.');
                // Update local status
                setJobs(prev => prev.map(j => j.url === job.url ? { ...j, status: 'applied' } : j));
              } else {
                Alert.alert('Error al postular', json.message || json.detail || 'Ocurrió un problema durante el envío.');
              }
            } catch (error) {
              Alert.alert('Error de red', 'No se pudo conectar con el servidor.');
            } finally {
              setApplyingUrl(null);
            }
          }
        }
      ]
    );
  };

  // Fetch History of Applications
  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await fetch(`${serverUrl}/applications?limit=50`);
      const json = await response.json();
      if (response.ok && json.status === 'success') {
        setHistory(json.data || []);
      }
    } catch (error) {
      console.log('Error fetching history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory();
    }
  }, [activeTab]);

  const onRefresh = async () => {
    setRefreshing(true);
    await checkHealth();
    if (activeTab === 'history') {
      await fetchHistory();
    }
    setRefreshing(false);
  };

  // Save Settings Modal
  const saveServerSettings = async () => {
    let formatted = tempServerUrl.trim();
    if (!formatted.startsWith('http://') && !formatted.startsWith('https://')) {
      formatted = `http://${formatted}`;
    }
    setServerUrl(formatted);
    setIsSettingsVisible(false);
    const connected = await checkHealth(formatted);
    if (connected) {
      Alert.alert('Servidor Conectado', `Conexión establecida con ${formatted}`);
    } else {
      Alert.alert('Advertencia', `No se pudo responder a /health en ${formatted}. Revisa la IP y el puerto.`);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* App Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleContainer}>
          <Ionicons name="rocket-sharp" size={24} color="#6366f1" />
          <Text style={styles.headerTitle}>CV Auto Mobile</Text>
        </View>

        <View style={styles.headerRight}>
          {/* Health Status Badge */}
          <TouchableOpacity onPress={() => checkHealth()} style={styles.statusBadge}>
            <View style={[styles.statusDot, { backgroundColor: isOnline ? '#10b981' : '#ef4444' }]} />
            <Text style={styles.statusText}>{isOnline ? 'Online' : 'Offline'}</Text>
          </TouchableOpacity>

          {/* Settings Button */}
          <TouchableOpacity onPress={() => { setTempServerUrl(serverUrl); setIsSettingsVisible(true); }} style={styles.iconButton}>
            <Ionicons name="settings-outline" size={22} color="#94a3b8" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Main Content Area */}
      <View style={styles.content}>
        {activeTab === 'search' && (
          <ScrollView
            contentContainerStyle={styles.scrollForm}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#6366f1" />}
          >
            <View style={styles.card}>
              <Text style={styles.cardTitle}>🔍 Buscar Vacantes en InfoJobs</Text>

              {/* Keywords Input */}
              <Text style={styles.label}>Puesto / Palabras Clave</Text>

              <View style={styles.inputContainer}>
                <Ionicons name="search-outline" size={18} color="#64748b" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={keywords}
                  onChangeText={setKeywords}
                  placeholder="Ej. Desarrollador Python, React"
                  placeholderTextColor="#64748b"
                />
              </View>

              {/* Location Input */}
              <Text style={styles.label}>Ubicación / Ciudad</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="location-outline" size={18} color="#64748b" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={location}
                  onChangeText={setLocation}
                  placeholder="Ej. Alicante, Madrid, Barcelona"
                  placeholderTextColor="#64748b"
                />
              </View>

              {/* Salary Min */}
              <Text style={styles.label}>Salario Mínimo Bruto (€/año)</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="cash-outline" size={18} color="#64748b" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={salaryMin}
                  onChangeText={setSalaryMin}
                  keyboardType="numeric"
                  placeholder="20000"
                  placeholderTextColor="#64748b"
                />
              </View>

              {/* Modality Selector */}
              <Text style={styles.label}>Modalidad de Trabajo</Text>
              <View style={styles.modalityContainer}>
                {['Todas', 'En remoto', 'Presencial', 'Híbrido'].map((item) => (
                  <TouchableOpacity
                    key={item}
                    style={[styles.modalityChip, modality === item && styles.modalityChipActive]}
                    onPress={() => setModality(item)}
                  >
                    <Text style={[styles.modalityChipText, modality === item && styles.modalityChipTextActive]}>
                      {item}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Allow Unspecified Salary Switch */}
              <View style={styles.switchRow}>
                <Text style={styles.switchLabel}>Permitir ofertas sin salario especificado</Text>
                <Switch
                  value={allowUnspecifiedSalary}
                  onValueChange={setAllowUnspecifiedSalary}
                  trackColor={{ false: '#334155', true: '#6366f1' }}
                  thumbColor={allowUnspecifiedSalary ? '#ffffff' : '#94a3b8'}
                />
              </View>

              {/* Max Results */}
              <Text style={styles.label}>Máximo de Ofertas a Analizar</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="list-outline" size={18} color="#64748b" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={maxResults}
                  onChangeText={setMaxResults}
                  keyboardType="numeric"
                  placeholder="10"
                  placeholderTextColor="#64748b"
                />
              </View>

              {/* Submit Search Button */}
              <TouchableOpacity
                style={[styles.primaryButton, searching && styles.disabledButton]}
                onPress={handleSearchJobs}
                disabled={searching}
              >
                {searching ? (
                  <ActivityIndicator color="#ffffff" size="small" />
                ) : (
                  <>
                    <Ionicons name="play-sharp" size={18} color="#ffffff" style={{ marginRight: 8 }} />
                    <Text style={styles.primaryButtonText}>Buscar Ofertas</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        )}

        {activeTab === 'jobs' && (
          <View style={styles.tabContainer}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>
                Ofertas Encontradas ({jobs.length})
              </Text>
              <TouchableOpacity onPress={() => handleSearchJobs()} style={styles.reloadChip}>
                <Ionicons name="refresh-outline" size={14} color="#6366f1" />
                <Text style={styles.reloadChipText}>Re-buscar</Text>
              </TouchableOpacity>
            </View>

            {jobs.length === 0 ? (
              <View style={styles.emptyContainer}>
                <Ionicons name="briefcase-outline" size={56} color="#334155" />
                <Text style={styles.emptyTitle}>Sin Ofertas Cargadas</Text>
                <Text style={styles.emptySubtitle}>Realiza una búsqueda desde la pestaña de Búsqueda para consultar empleos.</Text>
                <TouchableOpacity style={styles.secondaryButton} onPress={() => setActiveTab('search')}>
                  <Text style={styles.secondaryButtonText}>Ir a Búsqueda</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <FlatList
                data={jobs}
                keyExtractor={(item, index) => item.id || item.url || index.toString()}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => (
                  <View style={styles.jobCard}>
                    <View style={styles.jobHeader}>
                      <Text style={styles.jobTitle} numberOfLines={2}>{item.title}</Text>
                    </View>

                    {item.platform && (
                      <View style={{ flexDirection: 'row', marginVertical: 4 }}>
                        <View style={[
                          styles.platformChip,
                          item.platform.includes('Jooble') ? { backgroundColor: '#9333ea' } :
                          item.platform.includes('Indeed') ? { backgroundColor: '#2563eb' } : { backgroundColor: '#059669' }
                        ]}>
                          <Text style={styles.platformChipText}>{item.platform}</Text>
                        </View>
                      </View>
                    )}

                    <View style={styles.jobMetaRow}>
                      <Ionicons name="business-outline" size={14} color="#94a3b8" />
                      <Text style={styles.jobMetaText}>{item.company || 'Empresa confidencial'}</Text>
                    </View>

                    <View style={styles.jobMetaRow}>
                      <Ionicons name="location-outline" size={14} color="#94a3b8" />
                      <Text style={styles.jobMetaText}>{item.location || 'Ubicación no especificada'}</Text>
                    </View>

                    {item.salary && (
                      <View style={styles.jobMetaRow}>
                        <Ionicons name="cash-outline" size={14} color="#10b981" />
                        <Text style={[styles.jobMetaText, { color: '#10b981', fontWeight: '600' }]}>{item.salary}</Text>
                      </View>
                    )}

                    {item.killer_questions && item.killer_questions.length > 0 && (
                      <View style={styles.questionsBadge}>
                        <Ionicons name="help-circle-outline" size={14} color="#f59e0b" />
                        <Text style={styles.questionsText}>{item.killer_questions.length} preguntas killer detectadas</Text>
                      </View>
                    )}

                    <View style={styles.jobCardFooter}>
                      <TouchableOpacity
                        style={[
                          styles.applyButton,
                          item.status === 'applied' && styles.appliedButton,
                          applyingUrl === item.url && styles.disabledButton
                        ]}
                        onPress={() => handleApplyToJob(item)}
                        disabled={applyingUrl === item.url || item.status === 'applied'}
                      >
                        {applyingUrl === item.url ? (
                          <ActivityIndicator color="#ffffff" size="small" />
                        ) : item.status === 'applied' ? (
                          <>
                            <Ionicons name="checkmark-circle" size={16} color="#ffffff" style={{ marginRight: 6 }} />
                            <Text style={styles.applyButtonText}>Inscrito</Text>
                          </>
                        ) : (
                          <>
                            <Ionicons name="paper-plane-outline" size={16} color="#ffffff" style={{ marginRight: 6 }} />
                            <Text style={styles.applyButtonText}>Postular Ahora</Text>
                          </>
                        )}
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              />
            )}
          </View>
        )}

        {activeTab === 'history' && (
          <View style={styles.tabContainer}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Historial de Postulaciones</Text>
              <TouchableOpacity onPress={fetchHistory} style={styles.reloadChip}>
                <Ionicons name="sync-outline" size={14} color="#6366f1" />
                <Text style={styles.reloadChipText}>Actualizar</Text>
              </TouchableOpacity>
            </View>

            {loadingHistory ? (
              <ActivityIndicator size="large" color="#6366f1" style={{ marginTop: 40 }} />
            ) : history.length === 0 ? (
              <View style={styles.emptyContainer}>
                <Ionicons name="folder-open-outline" size={56} color="#334155" />
                <Text style={styles.emptyTitle}>Sin Postulaciones Registradas</Text>
                <Text style={styles.emptySubtitle}>Las ofertas en las que te inscribas aparecerán registradas aquí.</Text>
              </View>
            ) : (
              <FlatList
                data={history}
                keyExtractor={(item, index) => item.id?.toString() || index.toString()}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => (
                  <View style={styles.historyCard}>
                    <View style={styles.historyHeader}>
                      <Text style={styles.historyTitle}>{item.job_title || 'Postulación InfoJobs'}</Text>
                      <View style={styles.appliedBadge}>
                        <Text style={styles.appliedBadgeText}>Inscrito</Text>
                      </View>
                    </View>
                    <Text style={styles.historyCompany}>{item.company || 'Empresa'}</Text>
                    <Text style={styles.historyDate}>📅 Registrado: {item.applied_at || item.created_at || 'Reciente'}</Text>
                  </View>
                )}
              />
            )}
          </View>
        )}
      </View>

      {/* Settings Modal */}
      <Modal visible={isSettingsVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>⚙️ Ajustes de Servidor</Text>
              <TouchableOpacity onPress={() => setIsSettingsVisible(false)}>
                <Ionicons name="close" size={24} color="#94a3b8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.label}>Dirección IP del Backend PC</Text>
            <Text style={styles.hintText}>Ingresa la URL o IP de tu ordenador en la red Wi-Fi (ej. http://192.168.1.50:8000).</Text>

            <View style={[styles.inputContainer, { marginTop: 12 }]}>
              <Ionicons name="globe-outline" size={18} color="#64748b" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                value={tempServerUrl}
                onChangeText={setTempServerUrl}
                placeholder="http://192.168.1.50:8000"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
              />
            </View>

            <TouchableOpacity style={styles.primaryButton} onPress={saveServerSettings}>
              <Text style={styles.primaryButtonText}>Guardar y Probar Conexión</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Bottom Navigation Bar */}
      <View style={styles.bottomNav}>
        <TouchableOpacity
          style={[styles.navTab, activeTab === 'search' && styles.navTabActive]}
          onPress={() => setActiveTab('search')}
        >
          <Ionicons name="search-outline" size={22} color={activeTab === 'search' ? '#6366f1' : '#64748b'} />
          <Text style={[styles.navTabText, activeTab === 'search' && styles.navTabTextActive]}>Búsqueda</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navTab, activeTab === 'jobs' && styles.navTabActive]}
          onPress={() => setActiveTab('jobs')}
        >
          <Ionicons name="briefcase-outline" size={22} color={activeTab === 'jobs' ? '#6366f1' : '#64748b'} />
          <Text style={[styles.navTabText, activeTab === 'jobs' && styles.navTabTextActive]}>Ofertas</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navTab, activeTab === 'history' && styles.navTabActive]}
          onPress={() => setActiveTab('history')}
        >
          <Ionicons name="time-outline" size={22} color={activeTab === 'history' ? '#6366f1' : '#64748b'} />
          <Text style={[styles.navTabText, activeTab === 'history' && styles.navTabTextActive]}>Historial</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a'
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#0f172a'
  },
  headerTitleContainer: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#f8fafc',
    marginLeft: 10
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    marginRight: 10
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6
  },
  statusText: {
    color: '#cbd5e1',
    fontSize: 12,
    fontWeight: '600'
  },
  iconButton: {
    padding: 6
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16
  },
  scrollForm: {
    paddingBottom: 30
  },
  card: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155'
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: 16
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#94a3b8',
    marginBottom: 6,
    marginTop: 12
  },
  hintText: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 6
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0f172a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
    paddingHorizontal: 12
  },
  inputIcon: {
    marginRight: 8
  },
  input: {
    flex: 1,
    color: '#f8fafc',
    paddingVertical: 12,
    fontSize: 14
  },
  modalityContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 6
  },
  modalityChip: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20
  },
  modalityChipActive: {
    backgroundColor: '#6366f1',
    borderColor: '#6366f1'
  },
  modalityChipText: {
    color: '#94a3b8',
    fontSize: 13,
    fontWeight: '500'
  },
  modalityChipTextActive: {
    color: '#ffffff',
    fontWeight: '700'
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingVertical: 4
  },
  switchLabel: {
    flex: 1,
    color: '#cbd5e1',
    fontSize: 13,
    marginRight: 10
  },
  primaryButton: {
    backgroundColor: '#6366f1',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 24
  },
  primaryButtonText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 15
  },
  disabledButton: {
    opacity: 0.6
  },
  tabContainer: {
    flex: 1
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f8fafc'
  },
  reloadChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#334155'
  },
  reloadChipText: {
    color: '#6366f1',
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30
  },
  emptyTitle: {
    color: '#f8fafc',
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16
  },
  emptySubtitle: {
    color: '#64748b',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20
  },
  secondaryButton: {
    marginTop: 20,
    backgroundColor: '#1e293b',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155'
  },
  secondaryButtonText: {
    color: '#6366f1',
    fontWeight: '600'
  },
  jobCard: {
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#334155'
  },
  jobHeader: {
    marginBottom: 8
  },
  jobTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#f8fafc',
    lineHeight: 22
  },
  jobMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4
  },
  jobMetaText: {
    color: '#94a3b8',
    fontSize: 13,
    marginLeft: 6
  },
  questionsBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#451a03',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 10
  },
  questionsText: {
    color: '#f59e0b',
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4
  },
  jobCardFooter: {
    marginTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#334155',
    paddingTop: 12
  },
  applyButton: {
    backgroundColor: '#10b981',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10
  },
  appliedButton: {
    backgroundColor: '#3b82f6'
  },
  applyButtonText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 14
  },
  historyCard: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#334155'
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  historyTitle: {
    color: '#f8fafc',
    fontSize: 15,
    fontWeight: '700',
    flex: 1
  },
  appliedBadge: {
    backgroundColor: '#064e3b',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6
  },
  appliedBadgeText: {
    color: '#34d399',
    fontSize: 11,
    fontWeight: '700'
  },
  historyCompany: {
    color: '#94a3b8',
    fontSize: 13,
    marginTop: 4
  },
  historyDate: {
    color: '#64748b',
    fontSize: 12,
    marginTop: 6
  },
  bottomNav: {
    flexDirection: 'row',
    backgroundColor: '#0f172a',
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    paddingVertical: 8
  },
  navTab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 4
  },
  navTabActive: {},
  navTabText: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 4,
    fontWeight: '500'
  },
  navTabTextActive: {
    color: '#6366f1',
    fontWeight: '700'
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    paddingHorizontal: 20
  },
  modalContent: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155'
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f8fafc'
  },
  platformChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    alignSelf: 'flex-start'
  },
  platformChipText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700'
  }
});
