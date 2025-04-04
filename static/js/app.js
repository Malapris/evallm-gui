// static/js/app.js
const { createApp, ref, onMounted } = Vue

const app = createApp({
    setup() {
        const models = ref([])
        const tests = ref([])
        const selectedTest = ref(null)
        const config = ref({
            models: [],
            system_prompts: {},
            user_prompts: {},
            contexts: {},
            seeds: [42],
            temperatures: [0.7],
            commentaire: "",
            resultats: [],
            nom_test: ""
        })
        const results = ref([])
        const loading = ref(false)
        const currentView = ref('config') // 'config' ou 'results'
        const resultFile = ref(null)
        const error = ref(null)

        // Chargement des modèles disponibles
        const loadModels = async () => {
            try {
                const response = await axios.get('/api/models')
                models.value = response.data.models
            } catch (error) {
                console.error('Erreur lors du chargement des modèles:', error)
                alert('Erreur lors du chargement des modèles')
            }
        }

        // Chargement des tests disponibles
        const loadTests = async () => {
            try {
                const response = await axios.get('/api/tests')
                tests.value = response.data.tests
            } catch (error) {
                console.error('Erreur lors du chargement des tests:', error)
                alert('Erreur lors du chargement des tests')
            }
        }

        // Chargement des résultats
        const loadResults = async () => {
            try {
                const response = await axios.get('/api/results')
                results.value = response.data
            } catch (error) {
                console.error('Erreur lors du chargement des résultats:', error)
                alert('Erreur lors du chargement des résultats')
            }
        }

        // Sélection d'un test
        const selectTest = (test) => {
            selectedTest.value = test
            config.value = {
                ...test.config,
                models: test.config.models || [],
                system_prompts: test.config.system_prompts || {},
                user_prompts: test.config.user_prompts || {},
                contexts: test.config.contexts || {},
                seeds: test.config.seeds || [42],
                temperatures: test.config.temperatures || [0.7],
                commentaire: test.config.commentaire || "",
                resultats: test.config.resultats || [],
                nom_test: test.name || ""
            }
        }

        // Conversion des seeds en tableau de nombres
        const parseSeeds = (seedsStr) => {
            if (Array.isArray(seedsStr)) return seedsStr
            return seedsStr.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
        }

        // Conversion des températures en tableau de nombres
        const parseTemperatures = (tempsStr) => {
            if (Array.isArray(tempsStr)) return tempsStr
            return tempsStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n))
        }

        // Lancement d'un test
        const runTest = async () => {
            loading.value = true
            error.value = null
            results.value = []
            
            try {
                // Conversion des seeds et températures
                const testConfig = {
                    ...config.value,
                    seeds: parseSeeds(config.value.seeds),
                    temperatures: parseTemperatures(config.value.temperatures)
                }
                console.log('Configuration envoyée:', testConfig)
                const response = await axios.post('/api/test', testConfig)
                results.value = response.data.results
                resultFile.value = response.data.result_file
                console.log("Test terminé avec succès. Résultats disponibles à:", resultFile.value)
                
                await loadResults()
                // Afficher la boîte de dialogue au lieu de l'alerte
                setTimeout(() => {
                    document.querySelector('dialog').showModal()
                }, 500)
            } catch (error) {
                console.error('Erreur lors du test:', error)
                console.error('Détails de l\'erreur:', error.response?.data)
                alert('Erreur lors du test: ' + (error.response?.data?.detail || error.message))
            } finally {
                loading.value = false
            }
        }

        // Ajout d'un prompt système
        const addSystemPrompt = () => {
            const id = `system_${Object.keys(config.value.system_prompts).length + 1}`
            config.value.system_prompts[id] = ''
        }

        // Ajout d'un prompt utilisateur
        const addUserPrompt = () => {
            const id = `user_${Object.keys(config.value.user_prompts).length + 1}`
            config.value.user_prompts[id] = ''
        }

        // Ajout d'un contexte
        const addContext = () => {
            const id = `context_${Object.keys(config.value.contexts).length + 1}`
            config.value.contexts[id] = ''
        }

        // Suppression d'un prompt système
        const removeSystemPrompt = (id) => {
            delete config.value.system_prompts[id]
        }

        // Suppression d'un prompt utilisateur
        const removeUserPrompt = (id) => {
            delete config.value.user_prompts[id]
        }

        // Suppression d'un contexte
        const removeContext = (id) => {
            delete config.value.contexts[id]
        }

        onMounted(() => {
            loadModels()
            loadTests()
            loadResults()
        })

        return {
            models,
            tests,
            selectedTest,
            config,
            results,
            loading,
            currentView,
            resultFile,
            loadModels,
            loadTests,
            loadResults,
            selectTest,
            runTest,
            addSystemPrompt,
            addUserPrompt,
            addContext,
            removeSystemPrompt,
            removeUserPrompt,
            removeContext,
            parseSeeds,
            parseTemperatures
        }
    },
    template: `
        <div class="container mx-auto px-4 py-8">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-3xl font-bold">evallm GUI</h1>
                <a href="/results" class="text-blue-500 hover:text-blue-700">
                    Voir tous les résultats
                </a>
            </div>
            
            <!-- Dialog pour les résultats -->
            <dialog ref="resultModal" class="w-1/2 p-0 rounded-lg shadow-xl">
                <div class="p-6">
                    <h2 class="text-xl font-bold mb-4">Test terminé avec succès</h2>
                    <p class="mb-6">Votre test a été exécuté avec succès. Les résultats sont disponibles.</p>
                    <div class="flex justify-end space-x-4">
                        <button @click="$refs.resultModal.close()" 
                                class="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300">
                            Fermer
                        </button>
                        <button @click="viewResults()" 
                                class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                            Voir les résultats
                        </button>
                    </div>
                </div>
            </dialog>

            <div v-if="currentView === 'config'" class="space-y-8">
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-semibold mb-4">Sélection du test</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div v-for="test in tests" :key="test.name" 
                             class="border rounded-lg p-4 cursor-pointer hover:bg-gray-50"
                             :class="{ 'border-blue-500': selectedTest?.name === test.name }"
                             @click="selectTest(test)">
                            <h3 class="font-medium">{{ test.name }}</h3>
                            <p class="text-sm text-gray-600">{{ test.description }}</p>
                        </div>
                    </div>
                </div>

                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-semibold mb-4">Configuration</h2>
                    
                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Modèles</label>
                        <select v-model="config.models" multiple class="w-full h-48 border rounded-md p-2 overflow-y-auto">
                            <option v-for="model in models" :key="model" :value="model" class="hover:bg-gray-100">
                                {{ model }}
                            </option>
                        </select>
                        <p class="text-sm text-gray-500 mt-2">
                            Utilisez Ctrl (ou Cmd) pour sélectionner plusieurs modèles
                        </p>
                        <div v-if="config.models.length > 0" class="mt-4">
                            <p class="font-medium">Modèles sélectionnés ({{ config.models.length }}) :</p>
                            <ul class="list-disc list-inside mt-2 text-gray-700">
                                <li v-for="model in config.models" :key="model">{{ model }}</li>
                            </ul>
                        </div>
                        <p v-else class="text-red-500 mt-4">Aucun modèle sélectionné</p>
                    </div>

                    <div class="bg-white rounded-lg shadow p-6">
                        <h2 class="text-xl font-semibold mb-4">Prompts système</h2>
                        <div v-for="(prompt, key) in config.system_prompts" :key="key" class="mb-4">
                            <div class="flex justify-between items-center mb-2">
                                <label class="block text-sm font-medium text-gray-700">Clé: {{ key }}</label>
                                <button @click="removeSystemPrompt(key)" 
                                        class="text-red-500 hover:text-red-700">
                                    Supprimer
                                </button>
                            </div>
                            <textarea v-model="config.system_prompts[key]" 
                                    class="w-full border rounded-md p-2 h-32 resize-y"
                                    placeholder="Entrez votre prompt système ici..."></textarea>
                        </div>
                        <button @click="addSystemPrompt" 
                                class="mt-2 bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600">
                            Ajouter un prompt système
                        </button>
                    </div>

                    <div class="bg-white rounded-lg shadow p-6">
                        <h2 class="text-xl font-semibold mb-4">Prompts utilisateur</h2>
                        <div v-for="(prompt, key) in config.user_prompts" :key="key" class="mb-4">
                            <div class="flex justify-between items-center mb-2">
                                <label class="block text-sm font-medium text-gray-700">Clé: {{ key }}</label>
                                <button @click="removeUserPrompt(key)" 
                                        class="text-red-500 hover:text-red-700">
                                    Supprimer
                                </button>
                            </div>
                            <textarea v-model="config.user_prompts[key]" 
                                    class="w-full border rounded-md p-2 h-32 resize-y"
                                    placeholder="Entrez votre prompt utilisateur ici..."></textarea>
                        </div>
                        <button @click="addUserPrompt" 
                                class="mt-2 bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600">
                            Ajouter un prompt utilisateur
                        </button>
                    </div>

                    <div class="bg-white rounded-lg shadow p-6">
                        <h2 class="text-xl font-semibold mb-4">Contextes</h2>
                        <div v-for="(context, key) in config.contexts" :key="key" class="mb-4">
                            <div class="flex justify-between items-center mb-2">
                                <label class="block text-sm font-medium text-gray-700">Clé: {{ key }}</label>
                                <button @click="removeContext(key)" 
                                        class="text-red-500 hover:text-red-700">
                                    Supprimer
                                </button>
                            </div>
                            <textarea v-model="config.contexts[key]" 
                                    class="w-full border rounded-md p-2 h-32 resize-y"
                                    placeholder="Entrez votre contexte ici..."></textarea>
                        </div>
                        <button @click="addContext" 
                                class="mt-2 bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600">
                            Ajouter un contexte
                        </button>
                    </div>

                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Seeds</label>
                        <input v-model="config.seeds" class="w-full border rounded-md p-2" placeholder="42,43,44">
                        <p class="text-sm text-gray-500 mt-1">Séparez les valeurs par des virgules</p>
                        <p class="text-sm font-medium mt-2">
                            {{ parseSeeds(config.seeds).length }} seed(s) valide(s)
                        </p>
                    </div>

                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Températures</label>
                        <input v-model="config.temperatures" class="w-full border rounded-md p-2" placeholder="0.7,0.8,0.9">
                        <p class="text-sm text-gray-500 mt-1">Séparez les valeurs par des virgules</p>
                        <p class="text-sm font-medium mt-2">
                            {{ parseTemperatures(config.temperatures).length }} température(s) valide(s)
                        </p>
                    </div>

                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Nom du test</label>
                        <input v-model="config.nom_test" class="w-full border rounded-md p-2" placeholder="Nom du test">
                        <p class="text-sm text-gray-500 mt-1">Ce nom sera utilisé pour les fichiers de résultats</p>
                    </div>

                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Commentaire</label>
                        <input v-model="config.commentaire" class="w-full border rounded-md p-2" placeholder="Commentaire">
                    </div>

                    <div class="mb-6 p-4 bg-gray-50 rounded-md">
                        <h3 class="text-lg font-medium mb-2">Résumé du test</h3>
                        <div class="grid grid-cols-2 gap-2 text-sm">
                            <div>Nom du test:</div>
                            <div class="font-medium">{{ config.nom_test || 'Non défini' }}</div>
                            <div>Modèles:</div>
                            <div class="font-medium">{{ config.models.length }}</div>
                            <div>Prompts système:</div>
                            <div class="font-medium">{{ Object.keys(config.system_prompts).length }}</div>
                            <div>Prompts utilisateur:</div>
                            <div class="font-medium">{{ Object.keys(config.user_prompts).length }}</div>
                            <div>Contextes:</div>
                            <div class="font-medium">{{ Object.keys(config.contexts).length }}</div>
                            <div>Seeds:</div>
                            <div class="font-medium">{{ parseSeeds(config.seeds).length }}</div>
                            <div>Températures:</div>
                            <div class="font-medium">{{ parseTemperatures(config.temperatures).length }}</div>
                            <div class="col-span-2 border-t my-2"></div>
                            <div class="font-bold">Total des tests:</div>
                            <div class="font-bold text-blue-600">
                                {{ config.models.length * 
                                   Object.keys(config.system_prompts).length * 
                                   Object.keys(config.user_prompts).length * 
                                   Object.keys(config.contexts).length * 
                                   parseSeeds(config.seeds).length * 
                                   parseTemperatures(config.temperatures).length }}
                            </div>
                        </div>
                    </div>

                    <button @click="runTest" :disabled="loading || config.models.length === 0" 
                            class="w-full bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 disabled:bg-gray-400">
                        {{ loading ? 'Chargement...' : 'Lancer le test' }}
                    </button>
                </div>
            </div>

            <div v-else class="space-y-8">
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-semibold mb-4">Résultats</h2>
                    <div v-if="resultFile" class="mb-4">
                        <a :href="resultFile" target="_blank" class="text-blue-500 hover:text-blue-700">
                            Voir les résultats détaillés
                        </a>
                    </div>
                    <div v-for="result in results" :key="result.id" class="mb-4 p-4 border rounded">
                        <h3 class="font-medium">Test #{{ result.id }}</h3>
                        <p class="text-sm text-gray-600">{{ result.timestamp }}</p>
                        <pre class="mt-2 p-2 bg-gray-50 rounded">{{ JSON.stringify(result.results, null, 2) }}</pre>
                    </div>
                </div>

                <button @click="currentView = 'config'" 
                        class="w-full bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600">
                    Retour à la configuration
                </button>
            </div>

            <footer class="mt-12 pt-4 border-t text-center text-gray-500">
                <p>
                    Par <span class="font-medium">Francis Malapris</span> - 
                    <a href="https://github.com/Malapris/evallm" 
                       target="_blank" 
                       class="text-blue-500 hover:text-blue-700">
                        GitHub
                    </a>
                </p>
            </footer>
        </div>
    `,
    methods: {
        // Affichage des résultats après un test
        viewResults() {
            if (this.resultFile) {
                window.open(this.resultFile, '_blank');
                this.$refs.resultModal.close();
            }
        }
    }
})

app.mount('#app')