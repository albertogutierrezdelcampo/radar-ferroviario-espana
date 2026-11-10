const map = L.map('map', { preferCanvas: true }).setView([40.35, -3.70], 6);

        // Base geográfica oscura y discreta: conserva costa, límites y núcleos urbanos,
        // sin relieve y con la red viaria muy atenuada para priorizar el ferrocarril.
        // Base oscura sin API key. ESRI aporta costa, límites administrativos y núcleos urbanos
        // con una cartografía sobria; la referencia se mantiene separada para priorizar el ferrocarril.
        const darkBaseLayer = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 16,
            opacity: 0.92,
            className: 'rail-dark-base',
            attribution: 'Tiles &copy; Esri | Renfe Data & ADIF'
        }).addTo(map);
        const geographicLabelsLayer = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 16,
            opacity: 0.88,
            pane: 'shadowPane',
            className: 'rail-dark-labels'
        }).addTo(map);

        // Capa ORM opcional: se crea, pero NO se añade al iniciar.
        const openRailwayLayer = L.tileLayer('https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png', {
            maxZoom: 19,
            opacity: 0.82,
            attribution: '&copy; <a href="https://www.openrailwaymap.org/">OpenRailwayMap</a>'
        });

        const adifGeoJsonLayer = L.layerGroup().addTo(map);
        const routesLayer = L.layerGroup().addTo(map);
        const trailHighlightLayer = L.layerGroup().addTo(map);
        const stationsLayer = L.layerGroup().addTo(map);
        const alertsLayer = L.layerGroup().addTo(map);
        const trainsLayer = L.layerGroup().addTo(map);

        let allTrains = [];
        window.addEventListener('error',event=>{console.error('UI runtime error:',event.error||event.message);setTimeout(()=>{if(!allTrains.length&&!trainsRequestPromise)fetchTrains()},300)});
        window.addEventListener('unhandledrejection',event=>{console.error('UI promise rejection:',event.reason);setTimeout(()=>{if(!allTrains.length&&!trainsRequestPromise)fetchTrains()},300)});

        // Startup watchdog is registered before optional controls. UI errors cannot block data loading.
        let startupCompleted = false;
        const guaranteedStartupTimer = setTimeout(() => {
            if (!startupCompleted) initialLoad().finally(() => { startupCompleted = true; });
        }, 0);
        let operatorData = {};
        const operatorRoutesLayer = L.layerGroup().addTo(map);
        const operatorStationsLayer = L.layerGroup().addTo(map);
        const estimatedTrainsLayer = L.layerGroup().addTo(map);
        let transitNetworks = {}, feveData = {trains:[]};
        const metroRoutesLayer = L.layerGroup().addTo(map), metroStationsLayer = L.layerGroup().addTo(map), metroEstimatedLayer = L.layerGroup().addTo(map);
        let trainsRequestPromise = null;
        let lastTrainSync = null;
        let allStations = [];
        let allRoutes = [];
        let allAlerts = [];
        let staticFullyLoaded = false;
        let currentTrackStage = 0;

        const TYPE_COLORS = {
            'AVE': '#0d6efd',             // Azul Alta Velocidad
            'Larga Distancia': '#fd7e14', // Naranja Alvia / Euromed / Intercity
            'Media Distancia': '#198754', // Verde Avant / MD / Regional / FEVE
            'Cercanías': '#dc3545'        // Rojo Cercanías / Rodalies
        };

        function getColor(type) {
            return TYPE_COLORS[type] || '#6c757d';
        }
        const CERCANIAS_PALETTES = {
            'Madrid': {'C1':'#62B5E5','C2':'#00843D','C3':'#7A3E2E','C4':'#003DA5','C4A':'#003DA5','C4B':'#003DA5','C5':'#F28C28','C7':'#E4002B','C8':'#E84A9B','C8A':'#E84A9B','C8B':'#E84A9B','C9':'#7B2CBF','C10':'#00A499'},
            'Barcelona': {'R1':'#009A44','R2':'#00A3E0','R2N':'#00A3E0','R2S':'#00A3E0','R3':'#E30613','R4':'#F39200','R7':'#A54A98','R8':'#8BC53F','RG1':'#6E2585','RT1':'#00A6A6','RT2':'#A35C00'},
            'València': {'C1':'#F5A623','C2':'#E30613','C3':'#7B2CBF','C4':'#00A3E0','C5':'#009A44','C6':'#6B4C3B'},
            'Bilbao': {'C1':'#E30613','C2':'#00A3E0','C3':'#009A44','C3F':'#7B2CBF','C4':'#F39200'},
            'Asturias': {'C1':'#E30613','C2':'#00A3E0','C3':'#009A44','C4':'#F39200','C5':'#7B2CBF','C6':'#A54A98','C7':'#00A6A6','C8':'#8BC53F'},
            'Cantabria': {'C1':'#E30613','C2':'#009A44','C3':'#00A3E0'},
            'Sevilla': {'C1':'#00A3E0','C2':'#009A44','C3':'#F39200','C4':'#E30613','C5':'#7B2CBF'},
            'Málaga': {'C1':'#00A3E0','C2':'#009A44'},
            'Cádiz': {'C1':'#00A3E0','C1A':'#7B2CBF'},
            'Murcia / Alicante': {'C1':'#E30613','C2':'#00A3E0','C3':'#009A44'},
            'Zaragoza': {'C1':'#00A3E0'},
            'San Sebastián': {'C1':'#E30613'},
            'Otros': {'C1':'#00A3E0','C2':'#009A44','C3':'#E30613','C4':'#F39200','C5':'#7B2CBF','C6':'#00A6A6','C7':'#A54A98','C8':'#8BC53F','C9':'#7A3E2E','C10':'#003DA5'}
        };
        const NUCLEUS_ZONES = [
            {name:'Madrid',lat:40.4168,lon:-3.7038,radius:115},{name:'Barcelona',lat:41.3874,lon:2.1686,radius:125},
            {name:'València',lat:39.4699,lon:-0.3763,radius:105},{name:'Bilbao',lat:43.2630,lon:-2.9350,radius:75},
            {name:'Asturias',lat:43.3614,lon:-5.8494,radius:105},{name:'Cantabria',lat:43.4623,lon:-3.8099,radius:75},
            {name:'Sevilla',lat:37.3891,lon:-5.9845,radius:95},{name:'Málaga',lat:36.7213,lon:-4.4214,radius:90},
            {name:'Cádiz',lat:36.5271,lon:-6.2886,radius:85},{name:'Murcia / Alicante',lat:38.10,lon:-0.85,radius:135},
            {name:'Zaragoza',lat:41.6488,lon:-0.8891,radius:65},{name:'San Sebastián',lat:43.3183,lon:-1.9812,radius:65}
        ];
        function normalizeLineCode(value){return String(value||'').toUpperCase().replace(/RODALIES|CERCAN[IÍ]AS|LINEA|LÍNEA|LINIA|\s|[-_.]/g,'');}
        function lineCode(obj){
            const text=`${obj.subtype||''} ${obj.route_id||''} ${obj.label||''} ${obj.name||''} ${obj.origin_dest||''}`.toUpperCase();
            const match=text.match(/(?:^|[^A-Z0-9])((?:C|R|RG|RT)\s*\d{1,2}(?:\s*[A-Z])?)(?=$|[^A-Z0-9])/);
            return match?normalizeLineCode(match[1]):'';
        }
        function haversineKm(a,b){const R=6371,dLat=(b.lat-a.lat)*Math.PI/180,dLon=(b.lon-a.lon)*Math.PI/180,sa=Math.sin(dLat/2),so=Math.sin(dLon/2);return 2*R*Math.asin(Math.sqrt(sa*sa+Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*so*so));}
        function nucleusOf(obj){
            const text=norm(`${obj.nucleo||''} ${obj.origin_dest||''} ${obj.route_id||''} ${obj.name||''}`);
            const aliases=[['Madrid',['madrid']],['Barcelona',['barcelona','rodalies','catalunya']],['València',['valencia','valència']],['Bilbao',['bilbao','bizkaia']],['Asturias',['asturias','oviedo','gijon']],['Cantabria',['cantabria','santander']],['Sevilla',['sevilla']],['Málaga',['malaga','málaga']],['Cádiz',['cadiz','cádiz']],['Murcia / Alicante',['murcia','alicante','alacant']],['Zaragoza',['zaragoza']],['San Sebastián',['san sebastian','donostia','gipuzkoa']]];
            for(const [name,keys] of aliases)if(keys.some(k=>text.includes(norm(k))))return name;
            const lat=Number(obj.lat??obj._lat),lon=Number(obj.lon??obj._lon);
            if(Number.isFinite(lat)&&Number.isFinite(lon)){const point={lat,lon};const zone=NUCLEUS_ZONES.map(z=>({...z,d:haversineKm(point,z)})).filter(z=>z.d<=z.radius).sort((a,b)=>a.d-b.d)[0];if(zone)return zone.name;}
            return 'Otros';
        }
        function cercaniasColor(obj){const code=lineCode(obj),nucleus=nucleusOf(obj),palette=CERCANIAS_PALETTES[nucleus]||CERCANIAS_PALETTES.Otros;return palette[code]||CERCANIAS_PALETTES.Otros[code]||TYPE_COLORS['Cercanías'];}
        function trainColor(t){return t.type==='Cercanías'?cercaniasColor(t):getColor(t.type);}
        function activeCercaniasLines(){
            const bounds=map.getBounds();const items=new Map();
            allTrains.filter(t=>t.type==='Cercanías'&&bounds.contains([t.lat,t.lon])).forEach(t=>{const code=lineCode(t);if(code)items.set(`${nucleusOf(t)}:${code}`,{code,nucleus:nucleusOf(t),color:cercaniasColor(t)});});
            return [...items.values()].sort((a,b)=>a.nucleus.localeCompare(b.nucleus,'es')||a.code.localeCompare(b.code,'es',{numeric:true}));
        }
        function updateCercaniasLegend(){
            const box=document.getElementById('cercanias-line-legend');if(!box)return;
            const lines=map.getZoom()>=9?activeCercaniasLines():[];
            box.innerHTML=lines.length?`<div class="line-legend-title">Líneas Cercanías · ${escapeHtml(lines[0].nucleus)}</div>${lines.map(x=>`<span><i style="background:${x.color}"></i>${x.code}</span>`).join('')}`:'';
            box.classList.toggle('d-none',!lines.length);
        }
        const filterIds=['flt-speed-min','flt-speed-max','flt-delay','flt-motion','flt-status','flt-line','flt-train','flt-area','flt-next','flt-source','flt-data','flt-sort'];
        function norm(v){return String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()}
        function trainSearchText(t){return norm([t.id,t.label,t.trip_id,t.route_id,t.subtype,t.type,t.origin_dest,t.next_stop,...(t.stops||[]).map(x=>x.name)].join(' '))}
        function activeAdvancedFilters(t){
            const min=Number(document.getElementById('flt-speed-min').value||0),max=Number(document.getElementById('flt-speed-max').value||400),speed=Number(t.speed||0);if(speed<min||speed>max)return false;
            const delay=Number(t.delay_min||0),dm=document.getElementById('flt-delay').value;if(dm==='early'&&delay>=0||dm==='ontime'&&delay!==0||dm==='minor'&&(delay<1||delay>5)||dm==='medium'&&(delay<6||delay>15)||dm==='major'&&delay<=15)return false;
            const motion=document.getElementById('flt-motion').value;if(motion==='moving'&&speed<=0||motion==='stopped'&&speed>0)return false;
            const status=document.getElementById('flt-status').value;if(status!=='all'&&!String(t.current_status).includes(status))return false;
            const line=norm(document.getElementById('flt-line').value);if(line&&!norm(`${lineCode(t)} ${t.subtype} ${t.route_id} ${t.type}`).includes(line))return false;
            const train=norm(document.getElementById('flt-train').value);if(train&&!norm(`${t.id} ${t.label} ${t.trip_id}`).includes(train))return false;
            const area=norm(document.getElementById('flt-area').value);if(area&&!trainSearchText(t).includes(area))return false;
            const next=norm(document.getElementById('flt-next').value);if(next&&!norm(t.next_stop).includes(next))return false;
            const source=document.getElementById('flt-source').value;if(source!=='all'&&!norm(t.speed_source).includes(norm(source)))return false;
            const data=document.getElementById('flt-data').value;if(data==='route'&&!t.route_id||data==='stops'&&!(t.stops||[]).length||data==='delay'&&(t.delay_min===null||t.delay_min===undefined))return false;
            return true;
        }
        function filterLabel(id){const e=document.getElementById(id);if(id==='flt-speed-min'&&Number(e.value)>0)return `Velocidad ≥ ${e.value}`;if(id==='flt-speed-max'&&Number(e.value)<400)return `Velocidad ≤ ${e.value}`;if(['flt-delay','flt-motion','flt-status','flt-source','flt-data'].includes(id)&&e.value!=='all')return e.options[e.selectedIndex].text;if(['flt-line','flt-train','flt-area','flt-next'].includes(id)&&e.value.trim())return `${e.previousElementSibling?.innerText||'Filtro'}: ${e.value.trim()}`;return ''}
        function updateFilterUI(){const values=filterIds.map(filterLabel).filter(Boolean);const disabledFleet=[...document.querySelectorAll('.train-filter:not(:checked)')].map(x=>`Oculto: ${x.value}`);values.push(...disabledFleet);const countEl=document.getElementById('filter-count');if(countEl)countEl.innerText=`${values.length} activo${values.length===1?'':'s'}`;const summaryEl=document.getElementById('filter-summary');if(summaryEl)summaryEl.innerHTML=values.map(x=>`<span class="summary-chip">${x}</span>`).join('');document.querySelectorAll('.quick-chip').forEach(x=>x.classList.remove('active'));}
        function resetAdvancedFilters(){clearStationTypes();document.getElementById('flt-speed-min').value=0;document.getElementById('flt-speed-max').value=400;['flt-delay','flt-motion','flt-status','flt-source','flt-data','flt-sort'].forEach(x=>document.getElementById(x).value=x==='flt-sort'?'none':'all');['flt-line','flt-train','flt-area','flt-next'].forEach(x=>document.getElementById(x).value='');updateFilterUI();renderTrains();}
        function applyPreset(name,button){resetAdvancedFilters();if(name==='moving')document.getElementById('flt-motion').value='moving';if(name==='delayed')document.getElementById('flt-delay').value='major';if(name==='ontime')document.getElementById('flt-delay').value='ontime';if(name==='fast')document.getElementById('flt-speed-min').value=200;if(name==='stopped')document.getElementById('flt-motion').value='stopped';if(name==='cercanias')document.getElementById('flt-line').value='Cercanías';updateFilterUI();button.classList.add('active');renderTrains();}
        function updateFilterSuggestions(){const lines=[...new Set(allTrains.flatMap(t=>[lineCode(t),t.subtype,t.type]).filter(Boolean))].sort();document.getElementById('line-suggestions').innerHTML=lines.map(x=>`<option value="${x}">`).join('');const areas=[...new Set(allTrains.flatMap(t=>[t.next_stop,...(t.stops||[]).map(x=>x.name)]).filter(x=>x&&x!=='En ruta'&&x!=='En tránsito'))].sort().slice(0,500);document.getElementById('area-suggestions').innerHTML=areas.map(x=>`<option value="${x}">`).join('')}

        function showTrainDetails(t){
            const panel=document.getElementById('train-details'); const stops=t.stops||[];
            const rows=stops.length?stops.map(x=>`<div class="stop-row ${x.relation}"><strong>${x.name}</strong><span class="float-end">${x.arrival||x.departure||''} ${x.delay_min>0?`<span class="text-warning">+${x.delay_min} min</span>`:''}</span><br><small>${x.relation==='previous'?'Anterior':x.relation==='current'?'Parada actual':'Posterior'}</small></div>`).join(''):'<div class="text-secondary small">El feed no publica la secuencia completa de paradas para este servicio.</div>';
            panel.innerHTML=`<button class="btn-close btn-close-white float-end" onclick="this.parentElement.classList.add('d-none')"></button><div class="line-chip d-inline-block mb-2" style="background:${trainColor(t)}">${t.type} · ${t.subtype}</div><h4>${t.label}</h4><div class="small mb-2"><b>Ruta:</b> ${t.origin_dest}<br><b>ID:</b> ${t.id} · <b>Trip:</b> ${t.trip_id||'N/D'}<br><b>Velocidad:</b> ${t.speed} km/h (${t.speed_source})<br><b>Rumbo:</b> ${bearingToCardinal(t.bearing)||'N/D'}<br><b>Retraso actual:</b> ${t.delay_min||0} min<br><b>Estado:</b> ${t.current_status}<br><b>Próxima parada:</b> ${t.next_stop}</div><hr><strong>Recorrido y puntualidad por parada</strong>${rows}`;
            panel.classList.remove('d-none');
        }

        function bearingToCardinal(deg) {
            if (deg === null || deg === undefined) return '';
            const dirs = ['↑ N', '↗ NE', '→ E', '↘ SE', '↓ S', '↙ SO', '← O', '↖ NO'];
            return dirs[Math.round(deg / 45) % 8] + ` (${Math.round(deg)}°)`;
        }

        // 1. Renderizar el Trazado Físico Real de las Vías por Tipo y Color
        function renderRoutes() {
            routesLayer.clearLayers();
            if (!document.getElementById('toggle-routes').checked) return;

            const orderPriority = { 'Media Distancia': 1, 'Larga Distancia': 2, 'Cercanías': 3, 'AVE': 4 };
            const sortedRoutes = [...allRoutes].sort((a, b) => (orderPriority[a.type] || 0) - (orderPriority[b.type] || 0));

            sortedRoutes.forEach(route => {
                if (!route || !Array.isArray(route.coords) || !route.coords.length) return;
                const routeLine = lineCode({subtype:route.name,route_id:route.name,label:route.name});
                const color = route.type === 'Cercanías' && routeLine ? cercaniasColor({...route,subtype:routeLine,_lat:route.coords?.[0]?.[0]?.[0],_lon:route.coords?.[0]?.[0]?.[1]}) : getColor(route.type);
                const isAve = route.type === 'AVE';
                const isCerc = route.type === 'Cercanías';

                const polyline = L.polyline(route.coords, {
                    color: color,
                    weight: isAve ? 4.6 : (isCerc ? 3.8 : 3.2),
                    opacity: isAve ? 0.98 : 0.92,
                    smoothFactor: 0.8
                });

                const gaugeInfo = route.gauge ? ` <span class="badge bg-secondary">${route.gauge}</span>` : '';
                polyline.bindTooltip(`<strong>${route.type}${routeLine?` · ${routeLine}`:''}</strong>: ${route.name}${gaugeInfo}`, { sticky: true });
                routesLayer.addLayer(polyline);
            });
        }

        // 2. Renderizar Estaciones ADIF / Renfe en Canvas
        function stationSearchScore(st, rawQuery) {
            const query=norm(rawQuery).trim();
            if(!query)return 1;
            const name=norm(st.name), code=norm(st.id), category=norm(st.category);
            if(name===query||code===query)return 100;
            if(name.startsWith(query))return 80;
            if(name.includes(query)||code.includes(query))return 60;
            const tokens=query.split(/\s+/).filter(Boolean);
            return tokens.every(token=>`${name} ${code} ${category}`.includes(token))?40:0;
        }
        function stationType(st){
            const text=norm(`${st.category||''} ${st.operator||''} ${st.name||''}`);
            if(/feve|ram|ancho metrico/.test(text))return 'feve';
            if(/metro|tmb|fgv|euskotren|sfm|mallorca/.test(text))return 'metro';
            if(/iryo|ouigo/.test(text))return 'open_access';
            if(/cercan|rodalies|proximidad/.test(text))return 'cercanias';
            return 'long_distance';
        }
        function selectedStationTypes(){return new Set([...document.querySelectorAll('.station-type-filter:checked')].map(x=>x.value));}
        function stationTypeColor(type){return {long_distance:'#3b82f6',cercanias:'#ef4444',feve:'#b7793c',open_access:'#e5007e',metro:'#8b5cf6'}[type]||'#64748b';}
        function updateStationVisibilityUI(){
            const selected=selectedStationTypes(),label=document.getElementById('station-visibility-label'),button=document.getElementById('station-visibility-button');
            if(label)label.innerText=selected.size?`Estaciones: ${selected.size} tipos`:'Estaciones: ocultas';
            button?.classList.toggle('has-selection',selected.size>0);
        }
        function toggleStationVisibility(event){event?.stopPropagation();document.getElementById('station-visibility-menu')?.classList.toggle('d-none');}
        function clearStationTypes(){document.querySelectorAll('.station-type-filter').forEach(x=>x.checked=false);updateStationVisibilityUI();renderStations();}
        function selectAllStationTypes(){document.querySelectorAll('.station-type-filter').forEach(x=>x.checked=true);updateStationVisibilityUI();renderStations();}
        function visibleStationData(){
            const query=document.getElementById('station-search')?.value||'',selected=selectedStationTypes();
            if(!query.trim()&&!selected.size)return [];
            return allStations
                .map(st=>({st,score:stationSearchScore(st,query)}))
                .filter(item=>item.score>0&&(query.trim()||selected.has(stationType(item.st))))
                .sort((a,b)=>b.score-a.score||String(a.st.name).localeCompare(String(b.st.name),'es'))
                .map(item=>item.st);
        }
        function addStationMarker(st){
            const isCore=String(st.category||'').toLowerCase().includes('principal'),type=stationType(st),typeColor=stationTypeColor(type);
            const marker=L.circleMarker([st.lat,st.lon],{radius:isCore?5:3,color:'#fff',weight:isCore?1.5:1,fillColor:typeColor,fillOpacity:.95});
            marker.bindPopup(`<div style="font-family:system-ui,sans-serif;font-size:13px"><span class="badge bg-dark mb-1">${st.category||'Estación ADIF'}</span><br><strong>Estación:</strong> ${st.name}<br><strong>Código ADIF:</strong> ${st.id}<br><small class="text-muted">Coord: ${Number(st.lat).toFixed(4)}, ${Number(st.lon).toFixed(4)}</small></div>`);
            stationsLayer.addLayer(marker);
        }
        function renderStations(){
            stationsLayer.clearLayers();
            const stations=visibleStationData();
            stations.forEach(addStationMarker);
            const counter=document.getElementById('cnt-stations');if(counter)counter.innerText=stations.length;
        }
        function highlightStationMatch(text, rawQuery){
            const original=String(text||''), query=norm(rawQuery).trim();if(!query)return escapeHtml(original);
            const normalized=norm(original);const idx=normalized.indexOf(query);if(idx<0)return escapeHtml(original);
            let rawStart=0,rawEnd=original.length,normPos=0;
            for(let i=0;i<original.length;i++){const chunk=norm(original[i]);if(normPos===idx)rawStart=i;normPos+=chunk.length;if(normPos>=idx+query.length){rawEnd=i+1;break;}}
            return `${escapeHtml(original.slice(0,rawStart))}<mark>${escapeHtml(original.slice(rawStart,rawEnd))}</mark>${escapeHtml(original.slice(rawEnd))}`;
        }
        function stationMatches(rawQuery, limit=12){
            const query=String(rawQuery||'').trim();if(!query)return [];
            return allStations.map(st=>({st,score:stationSearchScore(st,query)})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score||String(a.st.name).localeCompare(String(b.st.name),'es')).slice(0,limit).map(x=>x.st);
        }
        function showStationResults(){
            const input=document.getElementById('station-search'),panel=document.getElementById('station-search-results');if(!input||!panel)return;
            const query=input.value.trim(),matches=stationMatches(query);
            if(!query){panel.classList.add('d-none');panel.innerHTML='';return;}
            panel.innerHTML=matches.length?matches.map((st,i)=>`<button type="button" class="station-result" role="option" data-station-id="${escapeHtml(st.id)}" data-index="${i}"><span>${highlightStationMatch(st.name,query)}</span><small>${highlightStationMatch(st.id,query)} · ${escapeHtml(st.category||'Estación ADIF')}</small></button>`).join(''):`<div class="station-no-results">Sin coincidencias para “${escapeHtml(query)}”</div>`;
            panel.classList.remove('d-none');
        }
        function selectStationResult(st){
            if(!st)return;const input=document.getElementById('station-search');input.value=st.name;document.getElementById('station-search-results')?.classList.add('d-none');renderStations();map.setView([st.lat,st.lon],Math.max(12,map.getZoom()));setTimeout(()=>{stationsLayer.eachLayer(layer=>{const ll=layer.getLatLng?.();if(ll&&Math.abs(ll.lat-st.lat)<1e-5&&Math.abs(ll.lng-st.lon)<1e-5)layer.openPopup?.()})},140);
        }

        function focusStationSearch(){
            const query=document.getElementById('station-search')?.value||'';const exact=stationMatches(query,1)[0];if(exact)selectStationResult(exact);else showStationResults();
        }

        const RENFE_SERVICES=['AVE','AVLO','ALVIA','EUROMED','INTERCITY','TALGO','TORRE DEL ORO','TRENHOTEL','AVANT','MEDIA DISTANCIA','REGIONAL','REGIONAL EXPRÉS','PROXIMIDAD','FEVE/RAM','RENFE LD'];
        function normalizedRenfeService(t){
            const raw=String(t.subtype||'').toUpperCase();
            if(raw.includes('REGIONAL EXPR'))return 'REGIONAL EXPRÉS';
            if(raw==='MD')return 'MEDIA DISTANCIA';
            if(raw.includes('ALVIA/LD'))return 'ALVIA';
            if(raw.includes('LD/AVE')||raw==='LD')return 'RENFE LD';
            return RENFE_SERVICES.find(x=>raw.includes(x))||raw||'RENFE LD';
        }
        function selectedRenfeServices(){return new Set([...document.querySelectorAll('.renfe-service-filter:checked')].map(x=>x.value));}
        function populateRenfeServices(){
            const menu=document.getElementById('renfe-services-menu');if(!menu)return;
            const existing=new Set([...document.querySelectorAll('.renfe-service-filter')].map(x=>x.value));
            menu.innerHTML=RENFE_SERVICES.filter(x=>!existing.has(x)).map(x=>`<label><input checked class="renfe-service-filter" type="checkbox" value="${x}"><span></span>${x}<b data-service-count="${x}">0</b></label>`).join('');
            menu.querySelectorAll('.renfe-service-filter').forEach(x=>x.addEventListener('change',()=>{renderTrains();updateCompactMenuCounts()}));
        }
        function closeCompactMenus(){
            document.querySelectorAll('.compact-control-menu').forEach(menu=>{menu.classList.add('d-none');menu.style.left='';menu.style.right='';menu.style.top='';menu.style.position='';});
            document.querySelectorAll('.compact-menu-button').forEach(button=>{button.classList.remove('menu-open');button.setAttribute('aria-expanded','false')});
        }
        function toggleCompactMenu(event,id){
            event?.preventDefault();event?.stopPropagation();
            const target=document.getElementById(id),button=event?.currentTarget,willOpen=Boolean(target?.classList.contains('d-none'));
            closeCompactMenus();
            if(willOpen&&target){
                target.classList.remove('d-none');button?.classList.add('menu-open');button?.setAttribute('aria-expanded','true');
                const r=button.getBoundingClientRect(), menuWidth=Math.min(target.offsetWidth||430, window.innerWidth-24);
                let left=Math.max(12,Math.min(r.left,window.innerWidth-menuWidth-12));
                target.style.position='fixed';target.style.left=`${left}px`;target.style.right='auto';target.style.top=`${Math.min(r.bottom+7,window.innerHeight-80)}px`;
            }
        }
        function toggleRenfeServices(event){toggleCompactMenu(event,'renfe-services-menu');}
        function updateCompactMenuCounts(){
            const networkInputs=[...document.querySelectorAll('#networks-menu input')],renfeInputs=[...document.querySelectorAll('#renfe-services-menu .renfe-service-filter')];
            const net=document.getElementById('networks-active-count'),renfe=document.getElementById('renfe-active-count');
            const netActive=networkInputs.filter(x=>x.checked).length,renfeActive=renfeInputs.filter(x=>x.checked).length;
            if(net)net.innerText=netActive?`${netActive} activas`:'Ninguna';
            if(renfe)renfe.innerText=renfeActive===renfeInputs.length?'Todos':`${renfeActive}/${renfeInputs.length}`;
        }

        function updateRenfeServiceCounts(){
            const counts={};allTrains.forEach(t=>counts[normalizedRenfeService(t)]=(counts[normalizedRenfeService(t)]||0)+1);
            const r=document.getElementById('cnt-regional'),re=document.getElementById('cnt-regional-express');if(r)r.innerText=counts['REGIONAL']||0;if(re)re.innerText=counts['REGIONAL EXPRÉS']||0;
            document.querySelectorAll('[data-service-count]').forEach(el=>el.innerText=counts[el.dataset.serviceCount]||0);
        }

        // 3. Renderizar Trenes en Tiempo Real
        function renderTrains() {
            trainsLayer.clearLayers();
            const selectedTypes = ['AVE','Larga Distancia','Media Distancia','Cercanías'];
            const searchQuery = document.getElementById('search-input').value.trim().toLowerCase();

            const counts = { 'AVE': 0, 'Larga Distancia': 0, 'Media Distancia': 0, 'Cercanías': 0 };
            let movingCount = 0;

            allTrains.forEach(t => {
                if (counts[t.type] !== undefined) counts[t.type]++;
                if (t.speed > 0) movingCount++;
            });

            const familyCounterIds={'AVE':'cnt-ave','Larga Distancia':'cnt-ld','Media Distancia':'cnt-md','Cercanías':'cnt-cerc'};
            Object.entries(familyCounterIds).forEach(([type,id])=>{const el=document.getElementById(id);if(el)el.innerText=counts[type]||0});
            const speedCounter=document.getElementById('speed-counter');if(speedCounter)speedCounter.innerText=`⚡ ${movingCount} con velocidad > 0 km/h`;

            let filtered = allTrains.filter(t => {
                if (!selectedTypes.includes(t.type) || (!document.getElementById('f-feve')?.checked && isFeveTrain(t)) || !selectedRenfeServices().has(normalizedRenfeService(t)) || !activeAdvancedFilters(t)) return false;
                if (!searchQuery) return true;
                const haystack = `${t.id} ${t.label} ${t.subtype} ${t.type} ${t.origin_dest} ${t.next_stop} ${t.route_id}`.toLowerCase();
                return haystack.includes(searchQuery);
            });

            const sort=document.getElementById('flt-sort').value;if(sort==='delay_desc')filtered.sort((a,b)=>(b.delay_min||0)-(a.delay_min||0));if(sort==='speed_desc')filtered.sort((a,b)=>(b.speed||0)-(a.speed||0));if(sort==='speed_asc')filtered.sort((a,b)=>(a.speed||0)-(b.speed||0));if(sort==='name')filtered.sort((a,b)=>String(a.label).localeCompare(String(b.label),'es',{numeric:true}));
            updateFilterUI();
            const totalCounter=document.getElementById('total-counter');if(totalCounter)totalCounter.innerText=`${filtered.length} / ${allTrains.length} trenes`;

            filtered.forEach(train => {
                if (!train || !Number.isFinite(Number(train.lat)) || !Number.isFinite(Number(train.lon))) return;
                const color = trainColor(train);
                const zoom = map.getZoom();
                const moving = Number(train.speed || 0) > 1;
                const bearing = Number.isFinite(Number(train.bearing)) ? Number(train.bearing) : 0;
                const delayClass = Number(train.delay_min || 0) >= 15 ? ' delay-major' : (Number(train.delay_min || 0) >= 5 ? ' delay-medium' : '');
                const motionClass = moving ? ' is-moving' : ' is-stopped';
                const compact = zoom <= 6;
                const serviceRaw = String(train.subtype || train.type || '').toUpperCase();
                const serviceCode = serviceRaw.includes('REGIONAL EXPR') ? 'RE' : serviceRaw==='REGIONAL' ? 'REG' : serviceRaw.includes('AVLO') ? 'AVLO' : serviceRaw.includes('AVE') ? 'AVE' : serviceRaw.includes('ALVIA') ? 'ALV' : serviceRaw.includes('INTERCITY') ? 'IC' : serviceRaw.includes('EUROMED') ? 'EU' : serviceRaw.includes('AVANT') ? 'AVT' : serviceRaw.includes('PROXIMIDAD') ? 'PROX' : serviceRaw.includes('MEDIA') ? 'MD' : serviceRaw.includes('CERCAN') ? (lineCode(train) || 'C') : serviceRaw.slice(0,3);
                const width = compact ? 10 : Math.max(23, Math.min(35, 13 + serviceCode.length * 5));
                const height = compact ? 10 : 17;
                const glyph = compact
                    ? `<span class="train-dot" style="--train-color:${color}"></span>`
                    : `<span class="train-service-marker${motionClass}${delayClass}" style="--train-color:${color};--bearing:${bearing}deg">
                           <span class="train-service-direction"></span><span class="train-service-code">${serviceCode}</span>
                       </span>`;
                const icon = L.divIcon({
                    html: glyph,
                    className: 'train-marker-shell',
                    iconSize: [width, height],
                    iconAnchor: [width / 2, height / 2]
                });

                const delayBadge = train.delay_min > 0
                    ? `<span class="badge bg-warning text-dark">+${train.delay_min} min retraso</span>`
                    : `<span class="badge bg-success">En hora</span>`;

                const speedDisplay = train.speed > 0
                    ? `<strong class="text-primary">${train.speed} km/h</strong> <small class="text-muted">(${train.speed_source})</small>`
                    : `<span class="text-secondary">0 km/h <small>(${train.speed_source || 'Calculando en sig. actualización GPS'})</small></span>`;

                const bearingStr = train.bearing !== null && train.bearing !== undefined
                    ? `<br><strong>Rumbo:</strong> ${bearingToCardinal(train.bearing)}`
                    : '';

                const popupHtml = `
                    <div style="font-family: system-ui, sans-serif; font-size: 13px; min-width: 230px;">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge" style="background-color: ${color};">${train.type} (${train.subtype})</span>
                            ${delayBadge}
                        </div>
                        <hr class="my-1">
                        <strong>Tren / ID:</strong> ${train.label} <small class="text-muted">(#${train.id})</small><br>
                        <strong>Servicio / Ruta:</strong> ${train.origin_dest}<br>
                        <strong>Próxima parada:</strong> ${train.next_stop}<br>
                        <strong>Velocidad:</strong> ${speedDisplay}${bearingStr}<br>
                        <strong>Estado GTFS-RT:</strong> ${train.current_status}<br>
                        <small class="text-muted">Posición en vía: ${train.lat.toFixed(4)}, ${train.lon.toFixed(4)}</small>
                    </div>
                `;

                const marker = L.marker([train.lat, train.lon], { icon: icon });
                marker.bindPopup(popupHtml);

                marker.on('click', () => {
                    showTrainDetails(train);
                    trailHighlightLayer.clearLayers();
                    if (train.trail && train.trail.length > 1) {
                        const trailLine = L.polyline(train.trail, {
                            color: '#212529',
                            weight: 5,
                            opacity: 0.85,
                            dashArray: '4, 6'
                        });
                        trailHighlightLayer.addLayer(trailLine);
                    }
                });

                const tooltipSpeed = train.speed > 0 ? `${train.speed} km/h` : (train.speed_source === 'Esperando 2º tick GPS...' ? 'calc. vel...' : '0 km/h');
                marker.bindTooltip(`${train.subtype} | ${train.label} (${tooltipSpeed})`, { direction: 'top', offset: [0, -12], className: 'train-tooltip' });
                trainsLayer.addLayer(marker);
            });
        }

        // 4. Renderizar Avisos e Incidencias en Tiempo Real
        function renderAlerts() {
            alertsLayer.clearLayers();
            document.getElementById('cnt-alerts').innerText = allAlerts.length;
            document.getElementById('nav-alert-count').innerText = allAlerts.length;

            if (document.getElementById('toggle-alerts').checked) {
                allAlerts.forEach(al => {
                    const bg = al.severity === 'ALTA' ? '#dc3545' : (al.severity === 'MEDIA' ? '#fd7e14' : '#0dcaf0');
                    const icon = L.divIcon({
                        html: `<div class="alert-marker-pin" style="background-color: ${bg}; width: 24px; height: 24px;">⚠️</div>`,
                        className: '',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    });

                    const popupHtml = `
                        <div style="font-family: system-ui, sans-serif; font-size: 13px; max-width: 280px;">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="badge" style="background-color: ${bg};">INCIDENCIA ${al.severity}</span>
                                <small class="text-muted">${al.source}</small>
                            </div>
                            <strong>Ámbito:</strong> ${al.scope}<hr class="my-1">
                            <p class="mb-1 fw-semibold text-dark">${al.title}</p>
                            <div class="small text-secondary" style="max-height: 150px; overflow-y: auto;">${al.description}</div>
                        </div>
                    `;

                    const m = L.marker([al.lat, al.lon], { icon: icon });
                    m.bindPopup(popupHtml);
                    m.bindTooltip(`⚠️ ${al.scope}: ${al.title.slice(0, 65)}...`, { direction: 'top', offset: [0, -10] });
                    alertsLayer.addLayer(m);
                });
            }

            renderAlertsList();
        }

        function renderAlertsList() {
            const container = document.getElementById('alerts-list-container');
            const q = (document.getElementById('alert-filter-input')?.value || '').trim().toLowerCase();

            const filtered = allAlerts.filter(a => {
                if (!q) return true;
                return `${a.scope} ${a.title} ${a.description}`.toLowerCase().includes(q);
            });

            if (filtered.length === 0) {
                container.innerHTML = `<div class="text-muted small text-center py-3">No hay incidencias que coincidan con el filtro.</div>`;
                return;
            }

            container.innerHTML = filtered.map(al => {
                const sevClass = al.severity === 'ALTA' ? 'alert-card-alta' : (al.severity === 'INFO' ? 'alert-card-info' : '');
                const badgeClass = al.severity === 'ALTA' ? 'bg-danger' : (al.severity === 'MEDIA' ? 'bg-warning text-dark' : 'bg-info text-dark');
                return `
                    <div class="card shadow-sm alert-card-item ${sevClass}" onclick="focusOnAlert(${al.lat}, ${al.lon})">
                        <div class="card-body p-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="badge ${badgeClass}" style="font-size: 10px;">${al.severity}</span>
                                <small class="fw-bold text-secondary" style="font-size: 11px;">${al.scope}</small>
                            </div>
                            <div class="small fw-semibold text-dark mb-1" style="font-size: 12px;">${al.title}</div>
                            <div class="text-muted" style="font-size: 11px; max-height: 60px; overflow-y: auto;">${al.description}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function focusOnAlert(lat, lon) {
            map.flyTo([lat, lon], 11, { duration: 1.0 });
        }

        function toggleAlertsPanel() {
            const mapCol = document.getElementById('map-col');
            const alertsCol = document.getElementById('alerts-col');
            if (alertsCol.classList.contains('d-none')) {
                alertsCol.classList.remove('d-none');
                mapCol.classList.replace('col-lg-12', 'col-lg-9');
            } else {
                alertsCol.classList.add('d-none');
                mapCol.classList.replace('col-lg-9', 'col-lg-12');
            }
            setTimeout(() => map.invalidateSize(), 250);
        }

        // 5. Funciones para ADIF ArcGIS Hub
        function loadAdifCatalog() {
            const listEl = document.getElementById('adif-catalog-list');
            fetch('/api/adif/catalog')
                .then(r => r.json())
                .then(data => {
                    if (!data.success || !data.datasets || data.datasets.length === 0) {
                        listEl.innerHTML = `<div class="p-3 text-muted small">No se pudieron listar capas automáticas en este instante. Puedes pegar cualquier URL GeoJSON o FeatureServer de <a href="https://adif-equisyzeta.hub.arcgis.com/search" target="_blank">ADIF ArcGIS Hub</a> en la caja superior.</div>`;
                        return;
                    }
                    listEl.innerHTML = data.datasets.map(ds => {
                        const targetUrl = ds.geojson_url || ds.rest_url || '';
                        const btnHtml = targetUrl
                            ? `<button class="btn btn-sm btn-primary" onclick="loadAdifLayer('${targetUrl.replace(/'/g, "\\'")}', '${ds.title.replace(/'/g, "\\'")}')">Superponer en Mapa</button>`
                            : `<a href="${ds.web_url}" target="_blank" class="btn btn-sm btn-outline-secondary">Ver en Hub ↗</a>`;
                        return `
                            <div class="list-group-item d-flex justify-content-between align-items-start gap-2">
                                <div>
                                    <span class="badge bg-secondary mb-1">${ds.source}</span>
                                    <h6 class="mb-1 fw-bold small">${ds.title}</h6>
                                    <p class="mb-1 text-muted" style="font-size: 12px;">${ds.description || 'Conjunto de datos geográficos de ADIF.'}</p>
                                </div>
                                <div class="text-nowrap">${btnHtml}</div>
                            </div>
                        `;
                    }).join('');
                })
                .catch(err => {
                    listEl.innerHTML = `<div class="p-3 text-danger small">Error consultando catálogo ADIF: ${err}</div>`;
                });
        }

        function loadCustomAdifUrl() {
            const url = document.getElementById('custom-adif-url').value.trim();
            if (!url) return;
            loadAdifLayer(url, 'Capa ADIF Personalizada');
        }

        function loadAdifLayer(url, title) {
            const statusEl = document.getElementById('adif-loading-status');
            statusEl.classList.remove('d-none');
            statusEl.innerText = `Descargando geometrías de "${title}" desde ADIF ArcGIS...`;

            fetch(`/api/adif/layer?url=${encodeURIComponent(url)}`)
                .then(r => r.json())
                .then(data => {
                    statusEl.classList.add('d-none');
                    if (data.success && data.geojson) {
                        const layer = L.geoJSON(data.geojson, {
                            style: { color: '#6610f2', weight: 3, opacity: 0.85 },
                            pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
                                radius: 5, fillColor: '#6610f2', color: '#fff', weight: 1.5, fillOpacity: 0.9
                            }),
                            onEachFeature: (feature, lyr) => {
                                const props = feature.properties || {};
                                const rows = Object.entries(props).slice(0, 8).map(([k, v]) => `<strong>${k}:</strong> ${v}`).join('<br>');
                                lyr.bindPopup(`<div class="small"><strong>ADIF ArcGIS — ${title}</strong><hr class="my-1">${rows}</div>`);
                            }
                        });
                        adifGeoJsonLayer.addLayer(layer);
                        if (layer.getBounds && layer.getBounds().isValid()) {
                            map.fitBounds(layer.getBounds());
                        }
                        alert(`Capa "${title}" añadida correctamente al mapa.`);
                    } else {
                        alert(`Aviso al cargar capa ADIF: ${data.error || 'Formato no compatible'}`);
                    }
                })
                .catch(err => {
                    statusEl.classList.add('d-none');
                    alert(`Error cargando capa ADIF: ${err}`);
                });
        }

        function clearAdifLayers() {
            adifGeoJsonLayer.clearLayers();
        }

        function clearSearch() {
            document.getElementById('search-input').value = '';
            renderTrains();
        }

        let stationPollTimer = null;
        function fetchStations() {
            return fetch(`/api/stations?_=${Date.now()}`, {cache:'no-store'})
                .then(r => {if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()})
                .then(data => {
                    if (data.success) {
                        const incoming = Array.isArray(data.stations) ? data.stations : [];
                        // Sustituir y redibujar también cuando el catálogo crece tras la carga GTFS.
                        const catalogueChanged = incoming.length !== allStations.length || data.fully_loaded !== staticFullyLoaded;
                        allStations = incoming;
                        staticFullyLoaded = Boolean(data.fully_loaded);
                        if (catalogueChanged || !stationsLayer.getLayers().length) renderStations();
                        clearTimeout(stationPollTimer);
                        if (!staticFullyLoaded) stationPollTimer = setTimeout(fetchStations, 1800);
                    }
                })
                .catch(e => {console.error('Error estaciones:', e);clearTimeout(stationPollTimer);stationPollTimer=setTimeout(fetchStations,3000)});
        }

        function formatFeedTime(ts){if(!ts)return 'pendiente';const d=new Date(Number(ts)*1000);return Number.isNaN(d.getTime())?'pendiente':d.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});}
        function updateFeedIndicator(){const times=[...Object.values(operatorData),...Object.values(transitNetworks)].map(x=>Number(x.updated_at||0)).filter(Boolean),latest=times.length?Math.max(...times):0,b=document.getElementById('feed-update-indicator');if(b){b.innerText=`⟳ Feeds: ${formatFeedTime(latest)}`;b.classList.toggle('feed-stale',!latest||Date.now()/1000-latest>90000)}}
        function isFeveTrain(t){
            if(Boolean(t.is_feve)||/FEVE|RAM|ANCHO.?M[EÉ]TRICO/i.test(`${t.subtype||''} ${t.route_id||''} ${t.origin_dest||''}`))return true;
            const nucleus=norm(`${t.nucleo||''} ${t.origin_dest||''}`),code=lineCode(t);
            if(nucleus.includes('asturias')&&['C4','C5','C6','C7','C8','C9'].includes(code))return true;
            if(nucleus.includes('bilbao')&&['C4','R3B','B1'].includes(code))return true;
            if((nucleus.includes('san sebastian')||nucleus.includes('donostia'))&&['R3','E1','E2'].includes(code))return true;
            if((nucleus.includes('santander')||nucleus.includes('cantabria'))&&['C2','C3','R2','R3'].includes(code))return true;
            return false;
        }
        function updateAuxNetworkCounts(){
            const feveCount=allTrains.filter(isFeveTrain).length,el=document.getElementById('cnt-feve');
            if(el)el.innerText=feveCount;
            const toggle=document.getElementById('f-feve')?.closest('.fleet-toggle');
            if(toggle)toggle.title=feveCount?`${feveCount} trenes FEVE/RAM detectados en el feed Renfe GTFS-RT`:'El feed Renfe GTFS-RT no publica ahora vehículos FEVE/RAM identificables';
        }
        function selectedUrbanNetworks(){return new Set([...document.querySelectorAll('.urban-network-filter:checked')].map(x=>x.value));}
        function selectedUrbanLines(){return new Set([...document.querySelectorAll('.urban-line-filter:checked')].map(x=>`${x.dataset.network}:${x.value}`));}
        function urbanRouteCode(route){return String(route.short_name||route.label||route.route_id||route.name||'Línea').trim();}
        function urbanRouteEnabled(networkKey,route){const selected=selectedUrbanLines();return selected.has(`${networkKey}:${route.route_id}`)||selected.has(`${networkKey}:${urbanRouteCode(route)}`);}
        function renderUrbanFilters(){
            const list=document.getElementById('urban-filter-list');if(!list)return;
            list.innerHTML=Object.entries(transitNetworks).map(([key,data])=>{
                const routes=[],seen=new Set();(data.routes||[]).forEach(route=>{const id=String(route.route_id||route.id||urbanRouteCode(route));if(!seen.has(id)){seen.add(id);routes.push({id,label:urbanRouteCode(route),color:route.color||data.color})}});
                return `<section class="urban-network-card"><label class="urban-network-head"><input checked class="urban-network-filter" type="checkbox" value="${escapeHtml(key)}"><span style="--urban-color:${data.color}"></span><b>${escapeHtml(data.name)}</b><small>${data.loaded?'Disponible':data.loading?'Cargando':'No disponible'} · ${routes.length} líneas · ${data.estimated_trains?.length||0} trenes EST${data.estimated_trains?.some(t=>t.frequency_based)?' · frecuencias GTFS':''}</small></label><div class="urban-lines">${routes.map(route=>`<label><input checked class="urban-line-filter" data-network="${escapeHtml(key)}" type="checkbox" value="${escapeHtml(route.id)}"><i style="background:${route.color}"></i>${escapeHtml(route.label)}</label>`).join('')||'<small class="urban-no-lines">Sin líneas cargadas</small>'}</div></section>`;
            }).join('');
            list.querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{if(input.classList.contains('urban-network-filter')){const card=input.closest('.urban-network-card');card.querySelectorAll('.urban-line-filter').forEach(x=>x.checked=input.checked)}renderMetroNetwork();updateUrbanFilterCount()}));
            updateUrbanFilterCount();
        }
        function updateUrbanFilterCount(){const total=document.querySelectorAll('.urban-network-filter').length,active=document.querySelectorAll('.urban-network-filter:checked').length,el=document.getElementById('cnt-metro');if(el)el.innerText=`${active}/${total}`;}
        function openUrbanFilters(event){event?.stopPropagation();closeCompactMenus();document.getElementById('urban-filter-panel')?.classList.remove('d-none');renderUrbanFilters();}
        function closeUrbanFilters(){document.getElementById('urban-filter-panel')?.classList.add('d-none');}
        function setAllUrbanFilters(enabled){document.querySelectorAll('#urban-filter-panel input').forEach(x=>x.checked=enabled);renderMetroNetwork();updateUrbanFilterCount();}
        function renderMetroNetwork(){
            metroRoutesLayer.clearLayers();metroStationsLayer.clearLayers();metroEstimatedLayer.clearLayers();
            if(!document.getElementById('f-metro')?.checked)return;
            let enabledNetworks=selectedUrbanNetworks();
            if(!document.querySelector('.urban-network-filter'))enabledNetworks=new Set(Object.keys(transitNetworks));
            Object.entries(transitNetworks).forEach(([key,data])=>{
                if(!data.loaded||!enabledNetworks.has(key))return;
                const enabledRouteIds=new Set([...document.querySelectorAll(`.urban-line-filter[data-network="${CSS.escape(key)}"]:checked`)].map(x=>x.value));
                const hasLineControls=document.querySelectorAll(`.urban-line-filter[data-network="${CSS.escape(key)}"]`).length>0;
                (data.routes||[]).forEach(route=>{const routeId=String(route.route_id||route.id||urbanRouteCode(route));if(hasLineControls&&!enabledRouteIds.has(routeId))return;(route.coords||[]).forEach(seg=>{if(seg?.length>1)L.polyline(seg,{color:route.color||data.color,weight:4,opacity:.92}).bindTooltip(`<b>${escapeHtml(data.name)}</b><br>${escapeHtml(route.name)}`).addTo(metroRoutesLayer)})});
                (data.stations||[]).forEach(st=>L.circleMarker([st.lat,st.lon],{radius:3,color:'#fff',weight:1,fillColor:data.color,fillOpacity:.95}).bindTooltip(`${escapeHtml(data.name)} · ${escapeHtml(st.name)}`).addTo(metroStationsLayer));
                (data.estimated_trains||[]).forEach(t=>{if(hasLineControls&&!enabledRouteIds.has(String(t.route_id||'')))return;const icon=L.divIcon({className:'metro-est-shell',iconSize:[38,20],iconAnchor:[19,10],html:`<div class="metro-est" style="--metro-color:${data.color}">${escapeHtml(String(t.label||data.name.split(' ')[1]||'M').slice(0,5))}<small>EST</small></div>`});L.marker([t.lat,t.lon],{icon}).bindPopup(`<div class="estimated-warning">⚠ POSICIÓN ESTIMADA · NO GPS</div><b>${escapeHtml(data.name)} · ${escapeHtml(t.label||'')}</b><br>${escapeHtml(t.previous_stop)} → ${escapeHtml(t.next_stop)}<br><small>${escapeHtml(t.scheduled_departure)} → ${escapeHtml(t.scheduled_arrival)} · ${t.segment_progress}% del tramo</small>`).addTo(metroEstimatedLayer)});
            });
        }
        function networkStatusLabel(network){
            if(network.loading||network.status==='checking')return ['checking','Comprobando'];
            if(network.loaded&&network.using_cache)return ['cached','Caché'];
            if(network.loaded)return ['loaded','Disponible'];
            if(network.status==='error')return ['error','Error'];
            return ['pending','Pendiente'];
        }
        function formatNetworkDate(ts){if(!ts)return 'Sin actualización';const date=new Date(Number(ts)*1000);return Number.isNaN(date.getTime())?'Sin actualización':date.toLocaleString('es-ES');}
        function renderNetworkStatus(){
            const list=document.getElementById('network-status-list'),summary=document.getElementById('network-status-summary');if(!list)return;
            const networks=Object.values(transitNetworks),loaded=networks.filter(x=>x.loaded).length;
            if(summary)summary.innerHTML=`<b>${loaded}/${networks.length}</b> fuentes disponibles · Metro de Madrid usa CRTM como fallback público`;
            list.innerHTML=networks.map(network=>{const [statusClass,statusText]=networkStatusLabel(network);return `<article class="network-source-row"><span class="network-source-dot ${statusClass}"></span><div><strong>${escapeHtml(network.name)}</strong><small>${escapeHtml(network.source||'')} · ${escapeHtml(network.active_source||'sin fuente activa')}</small><small>${network.route_count||0} rutas · ${network.station_count||0} estaciones · ${network.trip_count||0} servicios</small></div><div class="network-source-meta"><span class="network-source-status ${statusClass}">${statusText}</span><small>${formatNetworkDate(network.updated_at)}</small></div>${network.error?`<details><summary>Detalle</summary><code>${escapeHtml(network.error)}</code></details>`:''}</article>`}).join('')||'<div class="schedule-empty">Todavía no se ha recibido el estado de las fuentes.</div>';
        }
        function openNetworkStatus(event){event?.stopPropagation();closeCompactMenus();document.getElementById('network-status-panel')?.classList.remove('d-none');renderNetworkStatus();}
        function closeNetworkStatus(){document.getElementById('network-status-panel')?.classList.add('d-none');}
        function fetchTransitNetworks(manual=false){return fetch(`/api/transit-networks?_=${Date.now()}`,{cache:'no-store'}).then(r=>r.json()).then(data=>{if(!data.success)return;transitNetworks=data.networks||{};feveData=data.feve||{trains:[]};const feveCount=Math.max(feveData.trains?.length||0,allTrains.filter(isFeveTrain).length);const feveEl=document.getElementById('cnt-feve');if(feveEl)feveEl.innerText=feveCount;const summary=data.network_summary||{};document.getElementById('cnt-metro').innerText=`${summary.loaded||0}/${summary.total||Object.keys(transitNetworks).length}`;const metroToggle=document.getElementById('f-metro')?.closest('.fleet-toggle');if(metroToggle)metroToggle.title=`${summary.loaded||0} de ${summary.total||0} redes urbanas cargadas. Las posiciones son estimadas por horario.`;if(!document.getElementById('urban-filter-panel')?.classList.contains('d-none')||!document.querySelector('.urban-network-filter'))renderUrbanFilters();renderMetroNetwork();renderNetworkStatus();updateFeedIndicator();if(Object.values(transitNetworks).some(x=>x.loading&&!x.loaded)&&!manual)setTimeout(fetchTransitNetworks,5000)}).catch(e=>{console.warn('Redes urbanas pendientes',e);const summary=document.getElementById('network-status-summary');if(summary)summary.innerText=`No se pudo consultar el estado: ${e.message}`});}
        function refreshAllFeeds(){const b=document.getElementById('feed-update-indicator');if(b)b.innerText='⟳ Renovando…';fetch('/api/feeds/refresh',{method:'POST'}).then(()=>setTimeout(()=>{fetchOperatorData();fetchTransitNetworks()},3500));}

        function selectedOperators(){return new Set([...document.querySelectorAll('.operator-filter:checked')].map(x=>x.value));}
        function renderOperatorNetwork(){
            operatorRoutesLayer.clearLayers();operatorStationsLayer.clearLayers();
            const enabled=selectedOperators();
            Object.entries(operatorData).forEach(([key,data])=>{
                if(!enabled.has(key)||!data.loaded)return;
                (data.routes||[]).forEach(route=>{
                    const color=route.color||data.color;
                    (route.coords||[]).forEach(segment=>{
                        if(!Array.isArray(segment)||segment.length<2)return;
                        L.polyline(segment,{color:'#07111d',weight:7,opacity:.85,interactive:false}).addTo(operatorRoutesLayer);
                        L.polyline(segment,{color,weight:4,opacity:.98,dashArray:key==='iryo'?'10 4':'7 3',smoothFactor:.8})
                          .bindTooltip(`<strong>${escapeHtml(data.name)}</strong><br>${escapeHtml(route.name)}<br><small>Ruta programada GTFS</small>`).addTo(operatorRoutesLayer);
                    });
                });
                (data.stations||[]).forEach(st=>{
                    const marker=L.circleMarker([st.lat,st.lon],{radius:4,color:'#fff',weight:1.2,fillColor:data.color,fillOpacity:.95});
                    marker.bindPopup(`<strong>${escapeHtml(st.name)}</strong><br><span style="color:${data.color};font-weight:800">${escapeHtml(data.name)}</span><br><small>Estación incluida en el GTFS del operador</small>`);
                    marker.addTo(operatorStationsLayer);
                });
            });
        }
        function renderEstimatedTrains(){
            estimatedTrainsLayer.clearLayers();
            const enabled=selectedOperators();
            Object.entries(operatorData).forEach(([key,data])=>{
                if(!enabled.has(key)||!data.loaded)return;
                (data.estimated_trains||[]).forEach(train=>{
                    if(!Number.isFinite(Number(train.lat))||!Number.isFinite(Number(train.lon)))return;
                    const code=key==='iryo'?'IRYO':'OUIGO';
                    const icon=L.divIcon({className:'estimated-train-shell',iconSize:[47,27],iconAnchor:[23,13],html:`<div class="estimated-train" style="--est-color:${train.color};--bearing:${Number(train.bearing||0)}deg"><span class="est-arrow"></span><b>${code}</b><small>EST</small></div>`});
                    const marker=L.marker([train.lat,train.lon],{icon,zIndexOffset:850});
                    marker.bindPopup(`<div class="estimated-popup"><div class="estimated-warning">⚠ POSICIÓN ESTIMADA · NO GPS</div><strong>${escapeHtml(train.operator)} ${escapeHtml(train.label||'')}</strong><br>${escapeHtml(train.origin)} → ${escapeHtml(train.destination)}<hr><b>Tramo:</b> ${escapeHtml(train.previous_stop)} → ${escapeHtml(train.next_stop)}<br><b>Horario:</b> ${escapeHtml(train.scheduled_departure)} → ${escapeHtml(train.scheduled_arrival)}<br><b>Progreso calculado:</b> ${train.segment_progress}%<br><small>${escapeHtml(train.position_source)}<br>Calculado: ${escapeHtml(train.updated_at)}</small></div>`);
                    marker.bindTooltip(`${escapeHtml(train.operator)} · ESTIMADO<br>${escapeHtml(train.previous_stop)} → ${escapeHtml(train.next_stop)}`,{direction:'top',offset:[0,-12],className:'estimated-tooltip'});
                    marker.addTo(estimatedTrainsLayer);
                });
            });
        }

        function renderScheduleList(){
            const list=document.getElementById('schedule-list'),status=document.getElementById('schedule-status');if(!list)return;
            const op=document.getElementById('schedule-operator')?.value||'all',q=norm(document.getElementById('schedule-search')?.value||'');
            const entries=[];
            Object.entries(operatorData).forEach(([key,data])=>{if(op!=='all'&&key!==op)return;(data.trips||[]).forEach(t=>{if(!q||norm(`${t.operator} ${t.origin} ${t.destination} ${t.headsign} ${t.label} ${(t.stops||[]).map(x=>x.name).join(' ')}`).includes(q))entries.push({...t,key,color:data.color})})});
            entries.sort((a,b)=>String(a.departure).localeCompare(String(b.departure)));
            const estimatedCount=Object.values(operatorData).reduce((n,x)=>n+(x.estimated_trains?.length||0),0);
            status.innerText=`${entries.length} servicios programados · ${estimatedCount} posiciones estimadas activas`;
            list.innerHTML=entries.slice(0,500).map(t=>`<button class="schedule-row" onclick="focusScheduledTrip('${escapeHtml(t.id)}')"><span class="schedule-time">${escapeHtml(t.departure||'--:--')}</span><span class="schedule-op" style="background:${t.color}">${escapeHtml(t.operator)}</span><span><b>${escapeHtml(t.origin)} → ${escapeHtml(t.destination)}</b><small>${escapeHtml(t.label||'')} · llegada ${escapeHtml(t.arrival||'--:--')} · ${t.stops?.length||0} paradas</small></span></button>`).join('')||'<div class="schedule-empty">No hay servicios coincidentes.</div>';
        }
        function focusScheduledTrip(id){
            let trip=null;for(const data of Object.values(operatorData)){trip=(data.trips||[]).find(x=>x.id===id);if(trip)break;}if(!trip||!trip.stops?.length)return;
            const stationNames=new Set(trip.stops.map(x=>x.name));const points=[];Object.values(operatorData).forEach(data=>(data.stations||[]).forEach(st=>{if(stationNames.has(st.name))points.push([st.lat,st.lon])}));if(points.length)map.fitBounds(points,{padding:[70,70],maxZoom:9});
        }
        function toggleSchedulePanel(force){const p=document.getElementById('operator-schedule-panel');const open=typeof force==='boolean'?force:p.classList.contains('d-none');p.classList.toggle('d-none',!open);if(open)renderScheduleList();}
        function toggleOuigoConfig(force){const p=document.getElementById('ouigo-config-panel');const open=typeof force==='boolean'?force:p.classList.contains('d-none');p.classList.toggle('d-none',!open);if(open)document.getElementById('ouigo-api-key')?.focus();}
        function saveOuigoConfig(){
            const input=document.getElementById('ouigo-api-key'),status=document.getElementById('ouigo-config-status'),token=input.value.trim();
            if(!token){status.innerText='Introduce la API key del NAP.';return;}
            status.innerText='Guardando y descargando GTFS de OUIGO...';
            fetch('/api/operators/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})}).then(r=>r.json().then(d=>({ok:r.ok,data:d}))).then(({ok,data})=>{if(!ok)throw new Error(data.error||'No se pudo guardar');input.value='';status.innerText=data.message;setTimeout(()=>fetchOperatorData(),1800);setTimeout(()=>fetchOperatorData(),6000);setTimeout(()=>toggleOuigoConfig(false),6500)}).catch(e=>status.innerText=`Error: ${e.message}`);
        }

        function fetchOperatorData(){
            return fetch(`/api/operators?_=${Date.now()}`,{cache:'no-store'}).then(r=>r.json()).then(data=>{
                if(!data.success)return;operatorData=data.operators||{};
                document.getElementById('cnt-iryo').innerText=operatorData.iryo?.trips?.length||0;
                const ouigo=operatorData.ouigo||{};
                document.getElementById('cnt-ouigo').innerText=ouigo.configuration_required?'CFG':(ouigo.trips?.length||0);
                document.getElementById('f-ouigo').closest('.fleet-toggle')?.classList.toggle('operator-needs-config',Boolean(ouigo.configuration_required));
                const ouigoToggle=document.getElementById('f-ouigo').closest('.fleet-toggle');
                if(ouigo.configuration_required){ouigoToggle.title='Configurar API key oficial del NAP';ouigoToggle.onclick=e=>{e.preventDefault();toggleOuigoConfig(true)}}else{ouigoToggle.onclick=null;}
                renderOperatorNetwork();renderEstimatedTrains();renderScheduleList();updateFeedIndicator();
                if(Object.values(operatorData).some(x=>x.loading&&!x.loaded))setTimeout(fetchOperatorData,4000);
            }).catch(e=>console.warn('Operadores externos pendientes',e));
        }

        let routesPollTimer = null, routesRequest = null;
        function fetchRoutes() {
            if (routesRequest) return routesRequest;
            routesRequest = fetch(`/api/routes?_=${Date.now()}`, {cache:'no-store'})
                .then(r => {if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()})
                .then(data => {
                    if (data.success && Array.isArray(data.routes) && data.routes.length) {
                        allRoutes = data.routes;
                        currentTrackStage = Number(data.stage || 0);
                        renderRoutes();
                        const badgeEl=document.getElementById('tracks-badge');
                        if(badgeEl){badgeEl.className=currentTrackStage>=4?'badge bg-success text-white':'badge bg-warning text-dark';badgeEl.innerText=`🛤️ ${data.source}`;}
                        const diag=document.getElementById('diag-static');if(diag)diag.innerHTML=`<strong>Geometría Vías:</strong> ${data.source} | ${allStations.length} estaciones`;
                        clearTimeout(routesPollTimer);
                        if(currentTrackStage<4)routesPollTimer=setTimeout(fetchRoutes,5000);
                    }
                    return data;
                })
                .catch(e=>{console.error('Error rutas:',e);clearTimeout(routesPollTimer);routesPollTimer=setTimeout(fetchRoutes,4000);return null})
                .finally(()=>{routesRequest=null});
            return routesRequest;
        }

        // Viewport estable: una petición cada 900 ms, sólo al cambiar de celda/zoom y nunca en paralelo.
        let viewportRequest = null, lastViewportKey = '', lastViewportCenter = null, lastViewportZoom = 0;
        function fetchViewportTracksIfNeeded() {
            const z = map.getZoom(); if (currentTrackStage >= 4 || z < 9 || viewportRequest) return;
            const b = map.getBounds(), c = map.getCenter();
            if (b.getNorth()<35.5 || b.getSouth()>44.1 || b.getEast()<-10 || b.getWest()>4.8) return;
            if (lastViewportCenter && Math.abs(z-lastViewportZoom)<1 && c.distanceTo(lastViewportCenter)<25000) return;
            const q=.25, south=Math.floor(b.getSouth()/q)*q, west=Math.floor(b.getWest()/q)*q, north=Math.ceil(b.getNorth()/q)*q, east=Math.ceil(b.getEast()/q)*q;
            const key=`${z}:${south.toFixed(2)},${west.toFixed(2)},${north.toFixed(2)},${east.toFixed(2)}`;
            if(key===lastViewportKey)return; lastViewportKey=key; lastViewportCenter=c; lastViewportZoom=z;
            const bbox=`${south},${west},${north},${east}`;
            viewportRequest=fetch(`/api/routes/viewport?bbox=${encodeURIComponent(bbox)}`)
              .then(r=>r.json()).then(data=>{if(data.success&&data.added>0&&data.routes){allRoutes=data.routes;renderRoutes();}})
              .catch(()=>{}).finally(()=>{viewportRequest=null});
        }

        function fetchTrains() {
            // Single-flight: evita que inicio, temporizador y botones lancen peticiones simultáneas.
            if (trainsRequestPromise) return trainsRequestPromise;
            const statusEl = document.getElementById('status-indicator');
            if (!allTrains.length) statusEl.innerText = 'Actualizando telemetría...';
            const snapParam = document.getElementById('toggle-snap').checked ? '1' : '0';

            trainsRequestPromise = fetch(`/api/trains?snap=${snapParam}`)
                .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
                .then(data => {
                    if (!data.success) throw new Error(data.error || 'Respuesta no válida');
                    if (Array.isArray(data.trains) && data.trains.length) {
                        allTrains = data.trains;
                        updateFilterSuggestions();
                        updateRenfeServiceCounts();
                        updateAuxNetworkCounts();
                        renderTrains();
                        lastTrainSync = new Date();
                    }
                    const nowStr = (lastTrainSync || new Date()).toLocaleTimeString('es-ES');
                    statusEl.innerText = `Sincronizado: ${nowStr}`;
                    if (data.diagnostics) {
                        const c = data.diagnostics.cercanias || {};
                        const n = data.diagnostics.nacional_ave_ld_md || {};
                        document.getElementById('diag-cercanias').innerHTML = `<strong>Cercanías:</strong> ${c.count || 0} trenes`;
                        document.getElementById('diag-nacional').innerHTML = `<strong>AVE/LD/MD:</strong> ${n.total || 0} trenes (${n.with_calculated_speed || 0} con vel. > 0 km/h)`;
                    }
                    return data;
                })
                .catch(err => {
                    console.error('Error trenes:', err);
                    // Si ya hay datos visibles, conservarlos y no mostrar un falso estado de fallo global.
                    if (allTrains.length && lastTrainSync) {
                        statusEl.innerText = `Sincronizado: ${lastTrainSync.toLocaleTimeString('es-ES')} · reintento pendiente`;
                    } else {
                        statusEl.innerText = 'Conectando con telemetría…';
                    }
                    return null;
                })
                .finally(() => { trainsRequestPromise = null; });
            return trainsRequestPromise;
        }

        function fetchAlerts() {
            return fetch('/api/alerts')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        allAlerts = data.alerts;
                        renderAlerts();
                        if (data.diagnostics) {
                            document.getElementById('diag-alerts').innerHTML =
                                `<strong>Incidencias activas:</strong> ${allAlerts.length} (${data.diagnostics.official_count || 0} avisos GTFS-RT)`;
                        }
                    }
                })
                .catch(err => console.error('Error avisos:', err));
        }

        document.querySelectorAll('.operator-filter').forEach(cb=>cb.addEventListener('change',()=>{renderOperatorNetwork();renderEstimatedTrains();updateFilterUI();updateCompactMenuCounts()}));
        document.getElementById('f-feve')?.addEventListener('change',()=>{renderTrains();updateCompactMenuCounts()});document.getElementById('f-metro')?.addEventListener('change',()=>{renderMetroNetwork();updateCompactMenuCounts()});
        document.getElementById('schedule-search')?.addEventListener('input',()=>{clearTimeout(window.scheduleDebounce);window.scheduleDebounce=setTimeout(renderScheduleList,130)});
        document.getElementById('schedule-operator')?.addEventListener('change',renderScheduleList);

        document.querySelectorAll('.compact-menu-button').forEach(button=>button.setAttribute('aria-expanded','false'));
        closeCompactMenus();
        populateRenfeServices();
        document.querySelectorAll('.renfe-service-filter').forEach(x=>x.addEventListener('change',()=>{renderTrains();updateCompactMenuCounts()}));
        document.addEventListener('click',e=>{if(!e.target.closest('.compact-more-controls'))closeCompactMenus()});updateCompactMenuCounts();
        document.addEventListener('keydown',e=>{if(e.key==='Escape')closeCompactMenus()});

        // Arranque protegido: se agenda antes de enlazar controles opcionales.
        // Así, un control ausente nunca impide solicitar rutas, trenes, estaciones y avisos.
        // Startup already registered near the core state variables.

        // Eventos de interfaz
        document.querySelectorAll('.train-filter').forEach(cb => {
            cb.addEventListener('change', () => {
                cb.closest('.fleet-toggle')?.classList.toggle('is-off', !cb.checked);
                updateFilterUI();
                renderTrains();
                renderRoutes();
            });
        });
        document.getElementById('toggle-routes')?.addEventListener('change',renderRoutes);
        document.getElementById('toggle-snap')?.addEventListener('change',fetchTrains);
        document.getElementById('toggle-alerts')?.addEventListener('change',renderAlerts);
        const ormToggle = document.getElementById('toggle-orm');
        function syncOrmLayer() {
            if (ormToggle.checked) {
                if (!map.hasLayer(openRailwayLayer)) openRailwayLayer.addTo(map);
            } else if (map.hasLayer(openRailwayLayer)) {
                map.removeLayer(openRailwayLayer);
            }
        }
        ormToggle?.addEventListener('change',syncOrmLayer);
        if(ormToggle){ormToggle.checked=false;syncOrmLayer();}
        document.querySelectorAll('.station-type-filter').forEach(cb=>cb.addEventListener('change',()=>{updateStationVisibilityUI();renderStations()}));
        updateStationVisibilityUI();
        document.addEventListener('click',e=>{if(!e.target.closest('.station-visibility-wrap'))document.getElementById('station-visibility-menu')?.classList.add('d-none')});
        const stationSearchInput=document.getElementById('station-search');
        stationSearchInput?.addEventListener('input',()=>{clearTimeout(window.stationSearchDebounce);window.stationSearchDebounce=setTimeout(()=>{renderStations();showStationResults()},120)});
        stationSearchInput?.addEventListener('focus',showStationResults);
        stationSearchInput?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();focusStationSearch()}else if(e.key==='Escape'){document.getElementById('station-search-results')?.classList.add('d-none')}});
        document.getElementById('station-search-button')?.addEventListener('click',()=>{showStationResults();focusStationSearch()});
        document.getElementById('station-search-clear')?.addEventListener('click',()=>{stationSearchInput.value='';document.getElementById('station-search-results')?.classList.add('d-none');renderStations();stationSearchInput.focus()});
        document.getElementById('station-search-results')?.addEventListener('click',e=>{const button=e.target.closest('.station-result');if(!button)return;const st=allStations.find(x=>String(x.id)===String(button.dataset.stationId));selectStationResult(st)});
        document.addEventListener('click',e=>{if(!e.target.closest('.station-search-wrap'))document.getElementById('station-search-results')?.classList.add('d-none')});
        map.whenReady(()=>{try{renderStations()}catch(e){console.warn('Estaciones pendientes',e)}});
        document.getElementById('search-input').addEventListener('input', renderTrains);
        let viewportDebounce=null;
        map.on('moveend zoomend',()=>{clearTimeout(viewportDebounce);viewportDebounce=setTimeout(fetchViewportTracksIfNeeded,900)});
        map.on('moveend zoomend',()=>{updateCercaniasLegend();if(map.getZoom()>=9)renderRoutes()});
        map.on('zoomend.trainIcons',()=>renderTrains());
        map.on('click',closeCompactMenus);

        filterIds.forEach(id=>{const el=document.getElementById(id);if(!el)return;el.addEventListener(el.tagName==='INPUT'?'input':'change',()=>{updateFilterUI();renderTrains()})});document.querySelectorAll('.quick-chip').forEach(btn=>btn.addEventListener('click',()=>applyPreset(btn.dataset.preset,btn)));function setFilterDrawer(open){const body=document.getElementById('filter-body'),backdrop=document.getElementById('filter-backdrop'),close=document.getElementById('drawer-close');body.classList.toggle('open',open);backdrop.classList.toggle('show',open);close.classList.toggle('show',open);document.body.style.overflow=open?'hidden':'';}
        function toggleFilterDrawer(event){if(event){event.preventDefault();event.stopPropagation();}setFilterDrawer(!document.getElementById('filter-body').classList.contains('open'));}
        function closeFilterDrawer(){setFilterDrawer(false);}
        document.addEventListener('keydown',e=>{if(e.key==='Escape')closeFilterDrawer()});
        // Arranque inicial y refresco periódico
        function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
        function formatUptime(seconds){seconds=Number(seconds||0);const h=Math.floor(seconds/3600),m=Math.floor((seconds%3600)/60);return `${h} h ${m} min`;}
        function loadDiagnostics(){
            return fetch(`/api/diagnostics?_=${Date.now()}`,{cache:'no-store'}).then(r=>r.json()).then(data=>{
                if(!data.success)throw new Error(data.error||'Diagnóstico no disponible');
                const c=data.counts||{}, b=data.background||{}, mirrors=data.overpass_mirrors||[];
                document.getElementById('diag-counts').innerHTML=`<strong>Datos:</strong> ${c.trains||0} trenes · ${c.stations||0} estaciones · ${c.routes||0} rutas · uptime ${formatUptime(data.uptime)}`;
                const paused=mirrors.filter(x=>x.cooldown_seconds>0).length;
                document.getElementById('diag-overpass').innerHTML=`<strong>Overpass:</strong> ${c.overpass_cache||0} consultas en caché · ${paused}/${mirrors.length} mirrors en pausa`;
                document.getElementById('diag-static').innerHTML=`<strong>Geometría:</strong> fase ${b.tracks_stage||0} · ${escapeHtml(b.tracks_source||'N/D')}`;
                const errors=data.errors||[];
                document.getElementById('diag-errors').innerHTML=errors.length?errors.map(e=>`<div class="diag-error-row ${String(e.level).toLowerCase()}"><span>${escapeHtml(e.timestamp)}</span><b>${escapeHtml(e.level)}</b><code>${escapeHtml(e.message)}</code></div>`).join(''):'<div class="diag-ok">✓ No hay errores registrados en esta ejecución.</div>';
                const kb=Math.round(((data.error_log||{}).size_bytes||0)/1024);
                document.getElementById('diag-log-meta').innerText=`${kb} KB · retención ${(data.error_log||{}).retention||''}`;
            }).catch(err=>{document.getElementById('diag-errors').innerHTML=`<div class="text-danger">No se pudo cargar el diagnóstico: ${escapeHtml(err.message)}</div>`});
        }
        function clearDiagnosticErrors(){
            if(!confirm('¿Limpiar el registro visible y el fichero actual de errores?'))return;
            fetch('/api/diagnostics/errors',{method:'DELETE'}).then(r=>r.json()).then(()=>loadDiagnostics());
        }

        async function initialLoad(attempt = 1) {
            const status = document.getElementById('status-indicator');
            if (attempt === 1 && trainsRequestPromise) return trainsRequestPromise;
            if (status) status.innerText = attempt === 1 ? 'Sincronizando datos...' : `Reintentando carga (${attempt}/4)...`;
            fetchStations();
            fetchOperatorData();
            fetchTransitNetworks();
            const jobs = [fetchRoutes(), fetchTrains(), fetchAlerts()];
            await Promise.allSettled(jobs);
            if (allTrains.length === 0 && attempt < 4) {
                setTimeout(() => initialLoad(attempt + 1), attempt * 3000);
            } else if (status && allTrains.length === 0) {
                status.innerText = 'Conectando con telemetría…';
            } else if (status && lastTrainSync) {
                status.innerText = `Sincronizado: ${lastTrainSync.toLocaleTimeString('es-ES')}`;
            }
        }
        setInterval(fetchTrains, 12000);
        setInterval(fetchAlerts, 25000);
        setInterval(fetchOperatorData, 60000);
        setInterval(fetchTransitNetworks, 60000);
