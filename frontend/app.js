/* =========================================================
   Kikos AI - lógica de la aplicación (CONECTADO A FASTAPI)
   ========================================================= */
(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);

  /* ---------------------------------------------------------
     1. ICONOS (dibujos SVG pequeños)
     --------------------------------------------------------- */
  const ICONOS = {
    panelLeft: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    home: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    chevronRight: '<path d="m9 18 6-6-6-6"/>',
    chevronDown: '<path d="m6 9 6 6 6-6"/>',
    messageSquare: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
    mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>',
    arrowUp: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    lightbulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
    fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    check: '<path d="M20 6 9 17l-5-5"/>'
  };

  function icono(nombre, tamano = 20) {
    return '<svg class="icon" viewBox="0 0 24 24" width="' + tamano + '" height="' + tamano +
      '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      ICONOS[nombre] + '</svg>';
  }

  document.querySelectorAll('[data-icon]').forEach((nodo) => {
    nodo.innerHTML = icono(nodo.dataset.icon, Number(nodo.dataset.size) || 20);
  });

  /* ---------------------------------------------------------
     2. MODELOS
     --------------------------------------------------------- */
  const MODELOS = {
    rapido:    { nombre: 'Rápido',    descripcion: 'Respuestas inmediatas',          icono: 'zap' },
    pensativo: { nombre: 'Pensativo', descripcion: 'Razona antes de responder',      icono: 'lightbulb' },
    ultra:     { nombre: 'Ultra',     descripcion: 'Máxima calidad y profundidad',   icono: 'sparkles' }
  };

  /* ---------------------------------------------------------
     3. DATOS (localStorage)
     --------------------------------------------------------- */
  const CLAVE_ALMACEN = 'kikos-ai-v2';

  function crearId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

  function crearProyectoGeneral() {
    return {
      id: crearId(), nombre: 'General', protegido: true, expandido: true,
      subproyectos: [{ id: crearId(), nombre: 'Preguntas rápidas', mensajes: [] }]
    };
  }

  function estadoInicial() {
    const general = crearProyectoGeneral();
    return { proyectos: [general], proyectoActivoId: general.id, subActivoId: general.subproyectos[0].id, modelo: 'pensativo', barraOculta: false };
  }

  function cargarEstado() {
    try {
      const bruto = localStorage.getItem(CLAVE_ALMACEN);
      if (!bruto) return estadoInicial();
      const datos = JSON.parse(bruto);
      if (!datos || !Array.isArray(datos.proyectos)) return estadoInicial();

      const proyectos = datos.proyectos.filter((p) => p && typeof p.id === 'string' && typeof p.nombre === 'string')
        .map((p) => ({
          id: p.id, nombre: p.nombre, protegido: !!p.protegido, expandido: p.expandido !== false,
          subproyectos: (Array.isArray(p.subproyectos) ? p.subproyectos : []).filter((s) => s && typeof s.id === 'string' && typeof s.nombre === 'string')
            .map((s) => ({ id: s.id, nombre: s.nombre, mensajes: Array.isArray(s.mensajes) ? s.mensajes : [] }))
        }));

      if (!proyectos.some((p) => p.protegido)) proyectos.unshift(crearProyectoGeneral());
      const proyecto = proyectos.find((p) => p.id === datos.proyectoActivoId) || proyectos[0];
      const sub = proyecto.subproyectos.find((s) => s.id === datos.subActivoId) || proyecto.subproyectos[0] || null;

      return { proyectos, proyectoActivoId: proyecto.id, subActivoId: sub ? sub.id : null, modelo: MODELOS[datos.modelo] ? datos.modelo : 'pensativo', barraOculta: !!datos.barraOculta };
    } catch (error) { return estadoInicial(); }
  }

  let avisoAlmacenMostrado = false;
  function guardar() {
    try { localStorage.setItem(CLAVE_ALMACEN, JSON.stringify(estado)); } 
    catch (error) { if (!avisoAlmacenMostrado) { avisoAlmacenMostrado = true; mostrarAviso('No se pudo guardar.'); } }
  }

  const estado = cargarEstado();
  const ui = { busqueda: '' };
  const borradores = {};
  const pendientes = new Map();

  /* ---------------------------------------------------------
     4. FUNCIONES AUXILIARES
     --------------------------------------------------------- */
  function buscarProyecto(id) { return estado.proyectos.find((p) => p.id === id) || null; }
  function buscarSub(subId) {
    for (const proyecto of estado.proyectos) {
      const sub = proyecto.subproyectos.find((s) => s.id === subId);
      if (sub) return { proyecto, sub };
    }
    return null;
  }
  function obtenerActivo() { return estado.subActivoId ? buscarSub(estado.subActivoId) : null; }
  function obtenerBorrador(subId) {
    if (!borradores[subId]) borradores[subId] = { texto: '', archivos: [] };
    return borradores[subId];
  }
  function normalizar(texto) { return texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  function formatearPeso(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
  function el(etiqueta, propiedades = {}, ...hijos) {
    const nodo = document.createElement(etiqueta);
    for (const [clave, valor] of Object.entries(propiedades)) {
      if (clave === 'class') nodo.className = valor;
      else if (clave === 'html') nodo.innerHTML = valor;
      else if (clave.startsWith('on')) nodo.addEventListener(clave.slice(2), valor);
      else if (valor === true) nodo.setAttribute(clave, '');
      else if (valor !== false && valor != null) nodo.setAttribute(clave, valor);
    }
    for (const hijo of hijos.flat()) {
      if (hijo == null || hijo === false) continue;
      nodo.append(hijo.nodeType ? hijo : document.createTextNode(hijo));
    }
    return nodo;
  }

  /* ---------------------------------------------------------
     5. AVISO PEQUEÑO
     --------------------------------------------------------- */
  let temporizadorAviso = null;
  function mostrarAviso(mensaje) {
    const aviso = $('#aviso');
    aviso.textContent = mensaje;
    aviso.classList.add('visible');
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => aviso.classList.remove('visible'), 4000);
  }

  /* ---------------------------------------------------------
     6. REFERENCIAS A ELEMENTOS DE LA PÁGINA
     --------------------------------------------------------- */
  const app = $('#app');
  const listaProyectos = $('#listaProyectos');
  const zonaChat = $('#zonaChat');
  const contenedorMensajes = $('#mensajes');
  const campoTexto = $('#texto');
  const btnEnviar = $('#btnEnviar');
  const btnAdjuntar = $('#btnAdjuntar');
  const btnMicrofono = $('#btnMicrofono');
  const inputArchivos = $('#inputArchivos');
  const contenedorAdjuntos = $('#adjuntos');

  /* ---------------------------------------------------------
     7. BARRA LATERAL
     --------------------------------------------------------- */
  function botonAccion(nombreIcono, titulo, alHacerClic, peligro) {
    return el('button', {
      type: 'button', class: 'fila-accion' + (peligro ? ' peligro' : ''), title: titulo, 'aria-label': titulo,
      html: icono(nombreIcono, 16), onclick: (evento) => { evento.stopPropagation(); alHacerClic(); }
    });
  }

  function renderBarraLateral() {
    const consulta = normalizar(ui.busqueda.trim());
    listaProyectos.replaceChildren();
    let mostrados = 0;

    estado.proyectos.forEach((proyecto) => {
      const coincideProyecto = !consulta || normalizar(proyecto.nombre).includes(consulta);
      const subs = consulta && !coincideProyecto ? proyecto.subproyectos.filter((s) => normalizar(s.nombre).includes(consulta)) : proyecto.subproyectos;
      if (consulta && !coincideProyecto && subs.length === 0) return;
      mostrados++;
      const expandido = consulta ? true : proyecto.expandido;
      const esActivo = proyecto.id === estado.proyectoActivoId;

      const fila = el('div', { class: 'fila fila-proyecto' + (esActivo ? ' activa' : '') },
        el('button', { type: 'button', class: 'fila-principal', 'aria-expanded': String(expandido), onclick: () => alternarProyecto(proyecto.id) },
          el('span', { class: 'flecha' + (expandido ? ' abierta' : ''), html: icono('chevronRight', 16) }),
          el('span', { class: 'fila-icono', html: icono(proyecto.protegido ? 'home' : 'folder', 18) }),
          el('span', { class: 'fila-texto' }, proyecto.nombre)
        ),
        el('div', { class: 'fila-acciones' },
          botonAccion('plus', 'Nuevo subproyecto', () => abrirNuevoSub(proyecto.id)),
          botonAccion('pencil', 'Editar proyecto', () => abrirEditarProyecto(proyecto.id)),
          !proyecto.protegido && botonAccion('trash', 'Eliminar proyecto', () => abrirEliminarProyecto(proyecto.id), true)
        )
      );

      const cajaSubs = el('div', { class: 'subproyectos' });
      if (expandido) {
        if (subs.length === 0) cajaSubs.append(el('p', { class: 'sub-vacio' }, 'Sin subproyectos'));
        subs.forEach((sub) => {
          const activo = sub.id === estado.subActivoId;
          cajaSubs.append(el('div', { class: 'fila fila-sub' + (activo ? ' activa' : '') },
            el('button', { type: 'button', class: 'fila-principal', 'aria-current': activo ? 'true' : false, onclick: () => elegirSub(sub.id) },
              el('span', { class: 'fila-icono', html: icono('messageSquare', 16) }),
              el('span', { class: 'fila-texto' }, sub.nombre),
              pendientes.has(sub.id) && el('span', { class: 'punto-vivo', title: 'Esperando respuesta' })
            ),
            el('div', { class: 'fila-acciones' },
              botonAccion('pencil', 'Editar subproyecto', () => abrirEditarSub(sub.id)),
              botonAccion('trash', 'Eliminar subproyecto', () => abrirEliminarSub(sub.id), true)
            )
          ));
        });
      }
      listaProyectos.append(el('div', { class: 'proyecto' }, fila, expandido ? cajaSubs : null));
    });
    if (mostrados === 0) listaProyectos.append(el('p', { class: 'sin-resultados' }, consulta ? 'No hay resultados.' : 'Todavía no hay proyectos.'));
  }

  function alternarProyecto(id) {
    const proyecto = buscarProyecto(id);
    if (!proyecto) return;
    proyecto.expandido = !proyecto.expandido;
    guardar();
    renderBarraLateral();
  }

  /* ---------------------------------------------------------
     8. ZONA PRINCIPAL (Formateo y Render de mensajes)
     --------------------------------------------------------- */
  function renderCabecera() {
    const caja = $('#rutaActual');
    caja.replaceChildren();
    const proyecto = buscarProyecto(estado.proyectoActivoId);
    if (!proyecto) return;
    caja.append(el('span', { class: 'ruta-proyecto' }, proyecto.nombre));
    const activo = obtenerActivo();
    if (activo) caja.append(el('span', { class: 'ruta-sep', html: icono('chevronRight', 14) }), el('span', { class: 'ruta-sub' }, activo.sub.nombre));
  }

  function chipArchivo(archivo, alQuitar) {
    return el('span', { class: 'archivo' },
      el('span', { class: 'archivo-icono', html: icono('fileText', 16) }),
      el('span', { class: 'archivo-nombre', title: archivo.name || archivo.nombre }, archivo.name || archivo.nombre),
      el('span', { class: 'archivo-peso' }, formatearPeso(archivo.size != null ? archivo.size : archivo.peso)),
      alQuitar && el('button', { type: 'button', class: 'archivo-quitar', html: icono('x', 14), onclick: alQuitar })
    );
  }

  function formatearRespuesta(texto) {
    if (!texto) return '';
    let seguro = texto.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const blockRegex = /```(\w*)\n([\s\S]*?)```/g;
    return seguro.replace(blockRegex, function(match, lang, code) {
      return `
        <div style="background:#2a1d20; border-radius:12px; margin:12px 0; overflow:hidden; border:1px solid #d9cbce;">
          <div style="background:#f3eced; padding:8px 14px; font-family:monospace; font-size:0.85rem; color:#7b1e32; border-bottom:1px solid #d9cbce;">
              ${lang || 'código'}
          </div>
          <pre style="margin:0; padding:16px; overflow-x:auto; color:#fbf5f6; font-family:Consolas, monospace; font-size:0.95rem;"><code>${code}</code></pre>
        </div>
      `;
    });
  }

  function elementoMensaje(mensaje) {
    if (mensaje.rol === 'usuario') {
      const burbuja = el('div', { class: 'burbuja' });
      if (mensaje.archivos && mensaje.archivos.length) {
        burbuja.append(el('div', { class: 'burbuja-archivos' }, mensaje.archivos.map((a) => chipArchivo(a))));
      }
      if (mensaje.texto) burbuja.append(el('div', { class: 'msg-texto', html: formatearRespuesta(mensaje.texto) }));
      return el('div', { class: 'msg usuario' }, burbuja);
    }
    const modelo = MODELOS[mensaje.modelo];
    return el('div', { class: 'msg ia' },
      el('span', { class: 'avatar', html: icono('sparkles', 16) }),
      el('div', { class: 'msg-cuerpo' },
        el('div', { class: 'msg-texto', html: formatearRespuesta(mensaje.texto) }),
        modelo && el('span', { class: 'msg-meta' }, 'Modelo ' + modelo.nombre)
      )
    );
  }

  function elementoEscribiendo(claveModelo) {
    const etiqueta = claveModelo === 'rapido' ? '' : 'Analizando...';
    return el('div', { class: 'msg ia' },
      el('span', { class: 'avatar', html: icono('sparkles', 16) }),
      el('div', { class: 'msg-cuerpo' },
        el('div', { class: 'escribiendo' },
          el('span', { class: 'escribiendo-puntos' }, el('span'), el('span'), el('span')),
          etiqueta
        )
      )
    );
  }

  function renderMensajes() {
    contenedorMensajes.replaceChildren();
    const activo = obtenerActivo();

    if (!activo) {
      const proyecto = buscarProyecto(estado.proyectoActivoId);
      contenedorMensajes.append(el('div', { class: 'bienvenida' },
        el('div', { class: 'bienvenida-logo', html: icono('folder', 26) }),
        el('h1', {}, 'Proyecto sin subproyectos'),
        el('p', {}, 'Crea uno para empezar a chatear.'),
        proyecto && el('button', { type: 'button', class: 'btn btn-primario', onclick: () => abrirNuevoSub(proyecto.id) }, 'Crear subproyecto')
      ));
      return;
    }

    const { proyecto, sub } = activo;
    const espera = pendientes.has(sub.id);

    if (sub.mensajes.length === 0 && !espera) {
      contenedorMensajes.append(el('div', { class: 'bienvenida' },
        el('div', { class: 'bienvenida-logo', html: icono('sparkles', 28) }),
        el('h1', {}, '¿En qué puedo ayudarte hoy?'),
        el('p', {}, 'Estás en «' + sub.nombre + '»')
      ));
      return;
    }

    sub.mensajes.forEach((mensaje) => contenedorMensajes.append(elementoMensaje(mensaje)));
    if (espera) contenedorMensajes.append(elementoEscribiendo(pendientes.get(sub.id)));
    zonaChat.scrollTop = zonaChat.scrollHeight;
  }

  function renderAdjuntos() {
    contenedorAdjuntos.replaceChildren();
    const activo = obtenerActivo();
    if (!activo) return;
    const borrador = obtenerBorrador(activo.sub.id);
    borrador.archivos.forEach((archivo) => {
      contenedorAdjuntos.append(chipArchivo(archivo, () => {
        borrador.archivos = borrador.archivos.filter((a) => a !== archivo);
        renderAdjuntos();
        actualizarCompositor();
      }));
    });
  }

  function ajustarAltura() {
    campoTexto.style.height = 'auto';
    campoTexto.style.height = Math.min(campoTexto.scrollHeight, 200) + 'px';
  }

  function actualizarCompositor() {
    const activo = obtenerActivo();
    const hayChat = !!activo;
    campoTexto.disabled = !hayChat;
    btnAdjuntar.disabled = !hayChat;
    btnMicrofono.disabled = !hayChat;
    campoTexto.placeholder = hayChat ? 'Escribe tu pregunta a Kikos AI' : 'Crea un subproyecto para empezar';
    const esperando = hayChat && pendientes.has(activo.sub.id);
    const hayContenido = campoTexto.value.trim().length > 0 || (hayChat && obtenerBorrador(activo.sub.id).archivos.length > 0);
    btnEnviar.disabled = !hayChat || esperando || !hayContenido;
  }

  function guardarBorrador() {
    const activo = obtenerActivo();
    if (activo) obtenerBorrador(activo.sub.id).texto = campoTexto.value;
  }

  function cargarBorrador() {
    const activo = obtenerActivo();
    campoTexto.value = activo ? obtenerBorrador(activo.sub.id).texto : '';
    ajustarAltura();
  }

  function renderPrincipal() {
    renderCabecera();
    renderMensajes();
    cargarBorrador();
    renderAdjuntos();
    actualizarCompositor();
  }
  function renderTodo() { renderBarraLateral(); renderPrincipal(); }

  /* ---------------------------------------------------------
     9. CAMBIAR DE PROYECTO / SUBPROYECTO
     --------------------------------------------------------- */
  function activar(proyectoId, subId) {
    guardarBorrador();
    detenerMicrofono();
    estado.proyectoActivoId = proyectoId;
    estado.subActivoId = subId || null;
    guardar();
    renderTodo();
    if (subId && !esMovil()) campoTexto.focus();
  }

  function elegirSub(subId) {
    const encontrado = buscarSub(subId);
    if (!encontrado) return;
    if (estado.subActivoId !== subId) {
      encontrado.proyecto.expandido = true;
      activar(encontrado.proyecto.id, subId);
    }
    if (esMovil()) fijarBarra(false);
  }

  /* ---------------------------------------------------------
     10. VENTANA EMERGENTE
     --------------------------------------------------------- */
  const modal = {
    fondo: $('#modalFondo'), formulario: $('#modalForm'), titulo: $('#modalTitulo'), texto: $('#modalTexto'),
    campo: $('#modalCampo'), etiqueta: $('#modalEtiqueta'), input: $('#modalInput'), error: $('#modalError'),
    cancelar: $('#modalCancelar'), aceptar: $('#modalAceptar'), alAceptar: null, ultimoFoco: null
  };

  function abrirModal(opciones) {
    modal.ultimoFoco = document.activeElement;
    modal.titulo.textContent = opciones.titulo;
    modal.texto.textContent = opciones.texto || '';
    modal.campo.hidden = !opciones.etiqueta;
    modal.error.textContent = '';
    if (opciones.etiqueta) {
      modal.etiqueta.textContent = opciones.etiqueta;
      modal.input.value = opciones.valor || '';
      modal.input.placeholder = opciones.ejemplo || '';
    }
    modal.aceptar.textContent = opciones.botonAceptar;
    modal.aceptar.classList.toggle('peligro', !!opciones.peligro);
    modal.alAceptar = opciones.alAceptar;
    modal.fondo.hidden = false;
    if (opciones.etiqueta) { modal.input.focus(); modal.input.select(); }
    else modal.cancelar.focus();
  }

  function cerrarModal() {
    modal.fondo.hidden = true;
    modal.alAceptar = null;
    if (modal.ultimoFoco && modal.ultimoFoco.focus) modal.ultimoFoco.focus();
  }

  modal.formulario.addEventListener('submit', (evento) => {
    evento.preventDefault();
    const accion = modal.alAceptar;
    if (!modal.campo.hidden) {
      const nombre = modal.input.value.trim();
      if (!nombre) { modal.error.textContent = 'Escribe un nombre.'; modal.input.focus(); return; }
      cerrarModal();
      if (accion) accion(nombre);
    } else {
      cerrarModal();
      if (accion) accion();
    }
  });
  modal.cancelar.addEventListener('click', cerrarModal);
  modal.fondo.addEventListener('mousedown', (evento) => { if (evento.target === modal.fondo) cerrarModal(); });

  /* ---------------------------------------------------------
     11. ACCIONES: crear, editar y eliminar
     --------------------------------------------------------- */
  function abrirNuevoProyecto() {
    abrirModal({
      titulo: 'Nuevo proyecto', etiqueta: 'Nombre', ejemplo: 'Estudios', botonAceptar: 'Crear',
      alAceptar: (nombre) => {
        const sub = { id: crearId(), nombre: 'Chat principal', mensajes: [] };
        const proyecto = { id: crearId(), nombre, protegido: false, expandido: true, subproyectos: [sub] };
        estado.proyectos.push(proyecto);
        activar(proyecto.id, sub.id);
        if (esMovil()) fijarBarra(false);
      }
    });
  }

  function abrirNuevoSub(proyectoId) {
    const proyecto = buscarProyecto(proyectoId);
    if (!proyecto) return;
    abrirModal({
      titulo: 'Nuevo subproyecto', etiqueta: 'Nombre', ejemplo: 'Apuntes', botonAceptar: 'Crear',
      alAceptar: (nombre) => {
        const sub = { id: crearId(), nombre, mensajes: [] };
        proyecto.subproyectos.push(sub);
        proyecto.expandido = true;
        activar(proyecto.id, sub.id);
        if (esMovil()) fijarBarra(false);
      }
    });
  }

  function abrirEditarProyecto(proyectoId) {
    const proyecto = buscarProyecto(proyectoId);
    if (!proyecto) return;
    abrirModal({
      titulo: 'Editar proyecto', etiqueta: 'Nombre', valor: proyecto.nombre, botonAceptar: 'Guardar',
      alAceptar: (nombre) => { proyecto.nombre = nombre; guardar(); renderBarraLateral(); renderCabecera(); }
    });
  }

  function abrirEditarSub(subId) {
    const encontrado = buscarSub(subId);
    if (!encontrado) return;
    abrirModal({
      titulo: 'Editar subproyecto', etiqueta: 'Nombre', valor: encontrado.sub.nombre, botonAceptar: 'Guardar',
      alAceptar: (nombre) => { encontrado.sub.nombre = nombre; guardar(); renderBarraLateral(); renderCabecera(); }
    });
  }

  function abrirEliminarProyecto(proyectoId) {
    const proyecto = buscarProyecto(proyectoId);
    if (!proyecto || proyecto.protegido) return;
    abrirModal({
      titulo: 'Eliminar proyecto', texto: '¿Seguro que quieres eliminar «' + proyecto.nombre + '»?', botonAceptar: 'Eliminar', peligro: true,
      alAceptar: () => {
        const eraActivo = estado.proyectoActivoId === proyectoId;
        estado.proyectos = estado.proyectos.filter((p) => p.id !== proyectoId);
        if (eraActivo) { const s = estado.proyectos[0]; s.expandido = true; activar(s.id, s.subproyectos[0] ? s.subproyectos[0].id : null); }
        else { guardar(); renderBarraLateral(); }
      }
    });
  }

  function abrirEliminarSub(subId) {
    const encontrado = buscarSub(subId);
    if (!encontrado) return;
    abrirModal({
      titulo: 'Eliminar', texto: '¿Seguro que quieres eliminar «' + encontrado.sub.nombre + '»?', botonAceptar: 'Eliminar', peligro: true,
      alAceptar: () => {
        const { proyecto } = encontrado;
        const eraActivo = estado.subActivoId === subId;
        proyecto.subproyectos = proyecto.subproyectos.filter((s) => s.id !== subId);
        if (eraActivo) { activar(proyecto.id, proyecto.subproyectos[0] ? proyecto.subproyectos[0].id : null); }
        else { guardar(); renderBarraLateral(); }
      }
    });
  }

  /* ---------------------------------------------------------
     12. MOTOR: CONEXIÓN REAL CON FASTAPI Y OMNIROUTE
     --------------------------------------------------------- */
  let tokenAuth = null;

  async function asegurarLogin() {
    if (tokenAuth) return true;
    try {
      const res = await fetch('/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', password: 'admin123' })
      });
      const data = await res.json();
      if (data.status === 'success') { tokenAuth = data.token; return true; }
    } catch (error) { console.error("Error en login silencioso:", error); }
    return false;
  }

  async function procesarArchivoLocal(archivo) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error("Error leyendo " + archivo.name));
      if (archivo.type.startsWith('image/')) reader.readAsDataURL(archivo);
      else reader.readAsText(archivo);
    });
  }

  async function obtenerRespuestaIA({ texto, archivos, modelo }) {
    const logueado = await asegurarLogin();
    if (!logueado) return "Error: No se pudo conectar. Verifica que el servidor FastAPI esté encendido.";

    let attachments = [];
    let images = [];

    // Formatear archivos para el backend
    for (const archivo of archivos) {
      try {
        const contenido = await procesarArchivoLocal(archivo);
        if (archivo.type.startsWith('image/')) images.push({ name: archivo.name, data: contenido });
        else attachments.push({ name: archivo.name, content: contenido });
      } catch (e) { console.error(e); }
    }

    try {
      const payload = { prompt: texto || "", mode: modelo, workspace: "default" };
      if (attachments.length > 0) payload.attachments = attachments;
      if (images.length > 0) payload.images = images;

      const res = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tokenAuth },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') return data.reply;
      return "[Error]: " + (data.message || "Fallo interno en el motor Kikos.");
    } catch (error) {
      return "[Error]: Conexión rechazada. Asegúrate de que OmniRoute (puerto 8001) esté activo.";
    }
  }

  async function enviarMensaje() {
    const activo = obtenerActivo();
    if (!activo || pendientes.has(activo.sub.id)) return;

    const texto = campoTexto.value.trim();
    const borrador = obtenerBorrador(activo.sub.id);
    const archivos = borrador.archivos.slice();
    if (!texto && archivos.length === 0) return;

    detenerMicrofono();
    const subId = activo.sub.id;
    const modelo = estado.modelo;

    activo.sub.mensajes.push({ id: crearId(), rol: 'usuario', texto, archivos: archivos.map((a) => ({ nombre: a.name, peso: a.size })) });
    borrador.texto = ''; borrador.archivos = []; campoTexto.value = '';
    ajustarAltura(); renderAdjuntos();
    pendientes.set(subId, modelo);
    guardar(); renderBarraLateral(); renderMensajes(); actualizarCompositor();

    const respuesta = await obtenerRespuestaIA({ texto, archivos, modelo });

    pendientes.delete(subId);
    const destino = buscarSub(subId);
    if (destino && respuesta) {
      destino.sub.mensajes.push({ id: crearId(), rol: 'ia', texto: respuesta, modelo });
      guardar();
    }
    
    renderBarraLateral();
    if (estado.subActivoId === subId) { renderMensajes(); actualizarCompositor(); }
  }

  /* ---------------------------------------------------------
     13. SELECTOR DE MODELO
     --------------------------------------------------------- */
  const btnModelo = $('#btnModelo');
  const menuModelo = $('#menuModelo');

  function actualizarBotonModelo() {
    const modelo = MODELOS[estado.modelo];
    $('#iconoModelo').innerHTML = icono(modelo.icono, 16);
    $('#etiquetaModelo').textContent = modelo.nombre;
  }

  function renderMenuModelo() {
    menuModelo.replaceChildren();
    Object.entries(MODELOS).forEach(([clave, modelo]) => {
      const elegido = clave === estado.modelo;
      menuModelo.append(el('button', {
        type: 'button', class: 'opcion-modelo' + (elegido ? ' elegida' : ''), role: 'option', 'aria-selected': String(elegido),
        onclick: () => { estado.modelo = clave; guardar(); actualizarBotonModelo(); cerrarMenuModelo(); campoTexto.focus(); }
      },
        el('span', { class: 'opcion-icono', html: icono(modelo.icono, 20) }),
        el('span', { class: 'opcion-texto' }, el('strong', {}, modelo.nombre), el('small', {}, modelo.descripcion)),
        elegido && el('span', { class: 'opcion-check', html: icono('check', 16) })
      ));
    });
  }

  function cerrarMenuModelo() { menuModelo.hidden = true; btnModelo.setAttribute('aria-expanded', 'false'); }
  btnModelo.addEventListener('click', () => { const abrir = menuModelo.hidden; if (abrir) renderMenuModelo(); menuModelo.hidden = !abrir; btnModelo.setAttribute('aria-expanded', String(abrir)); });
  document.addEventListener('click', (evento) => { if (!evento.target.closest('.selector-modelo')) cerrarMenuModelo(); });

  /* ---------------------------------------------------------
     14. ARCHIVOS ADJUNTOS Y MICRÓFONO
     --------------------------------------------------------- */
  btnAdjuntar.addEventListener('click', () => inputArchivos.click());
  inputArchivos.addEventListener('change', () => {
    const activo = obtenerActivo();
    if (activo) {
      const borrador = obtenerBorrador(activo.sub.id);
      Array.from(inputArchivos.files).forEach((archivo) => {
        if (!borrador.archivos.some((a) => a.name === archivo.name)) borrador.archivos.push(archivo);
      });
      renderAdjuntos(); actualizarCompositor();
    }
    inputArchivos.value = '';
  });

  const Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;
  let reconocimiento = null;
  function pintarMicrofono(activo) { btnMicrofono.classList.toggle('grabando', activo); }
  function detenerMicrofono() {
    if (!reconocimiento) return;
    const actual = reconocimiento; reconocimiento = null; actual.onresult = null; actual.onerror = null; actual.onend = null;
    try { actual.abort(); } catch (error) {} pintarMicrofono(false);
  }

  btnMicrofono.addEventListener('click', () => {
    if (!Reconocimiento) return mostrarAviso('Tu navegador no permite dictar por voz.');
    if (reconocimiento) return reconocimiento.stop();
    const actual = new Reconocimiento(); reconocimiento = actual; actual.lang = 'es-ES'; actual.continuous = true;
    const textoInicial = campoTexto.value;
    actual.onstart = () => pintarMicrofono(true);
    actual.onresult = (evento) => {
      let dictado = ''; for (let i = 0; i < evento.results.length; i++) dictado += evento.results[i][0].transcript;
      campoTexto.value = (textoInicial.trimEnd() + ' ' + dictado.trim()).trim(); ajustarAltura(); actualizarCompositor();
    };
    actual.onerror = () => { mostrarAviso('No se pudo usar el micrófono.'); };
    actual.onend = () => { if (reconocimiento === actual) reconocimiento = null; pintarMicrofono(false); guardarBorrador(); };
    try { actual.start(); } catch (error) { reconocimiento = null; pintarMicrofono(false); }
  });

  /* ---------------------------------------------------------
     16. EVENTOS DE INTERFAZ Y BARRA
     --------------------------------------------------------- */
  const consultaMovil = window.matchMedia('(max-width: 768px)');
  function esMovil() { return consultaMovil.matches; }
  function fijarBarra(abierta) {
    if (esMovil()) app.classList.toggle('barra-abierta', abierta);
    else { app.classList.toggle('barra-oculta', !abierta); estado.barraOculta = !abierta; guardar(); }
  }
  function aplicarBarraInicial() { app.classList.remove('barra-abierta'); app.classList.toggle('barra-oculta', !esMovil() && estado.barraOculta); }

  $('#btnOcultar').addEventListener('click', () => fijarBarra(false));
  $('#btnMostrar').addEventListener('click', () => fijarBarra(true));
  $('#fondoOscuro').addEventListener('click', () => fijarBarra(false));
  if (consultaMovil.addEventListener) consultaMovil.addEventListener('change', aplicarBarraInicial); else consultaMovil.addListener(aplicarBarraInicial);

  const btnBuscar = $('#btnBuscar'), cajaBusqueda = $('#cajaBusqueda'), inputBusqueda = $('#inputBusqueda');
  function mostrarBusqueda(mostrar) {
    cajaBusqueda.hidden = !mostrar; btnBuscar.classList.toggle('activo', mostrar);
    if (mostrar) inputBusqueda.focus(); else { inputBusqueda.value = ''; ui.busqueda = ''; renderBarraLateral(); }
  }
  btnBuscar.addEventListener('click', () => mostrarBusqueda(cajaBusqueda.hidden));
  inputBusqueda.addEventListener('input', () => { ui.busqueda = inputBusqueda.value; renderBarraLateral(); });
  $('#btnNuevoProyecto').addEventListener('click', abrirNuevoProyecto);
  $('#formulario').addEventListener('submit', (e) => { e.preventDefault(); enviarMensaje(); });

  campoTexto.addEventListener('input', () => { ajustarAltura(); actualizarCompositor(); });
  campoTexto.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !window.matchMedia('(hover: none)').matches) { e.preventDefault(); if (!btnEnviar.disabled) enviarMensaje(); }
  });

  /* ---------------------------------------------------------
     ARRANQUE
     --------------------------------------------------------- */
  actualizarBotonModelo();
  aplicarBarraInicial();
  renderTodo();
})();
