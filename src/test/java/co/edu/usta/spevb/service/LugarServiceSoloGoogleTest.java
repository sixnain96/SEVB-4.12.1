package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import co.edu.usta.spevb.dto.LugarResponse;
import co.edu.usta.spevb.repository.LugarRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** 4.14: con la política «solo Google», ArcGIS, la base propia/catastro y Nominatim NO participan en la búsqueda del pasajero y no hay respaldo silencioso. */
class LugarServiceSoloGoogleTest {
    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);
    private LugarRepository repo; private GeocodingService geo; private DireccionesHibridasService hib; private DireccionesLocalesService loc; private GoogleDireccionesService google;
    private LugarService s;

    @BeforeEach void preparar() {
        repo = mock(LugarRepository.class); geo = mock(GeocodingService.class); hib = mock(DireccionesHibridasService.class);
        loc = mock(DireccionesLocalesService.class); google = mock(GoogleDireccionesService.class);
        when(google.activo()).thenReturn(true);
        when(hib.arcgisActivo()).thenReturn(true); when(hib.catastroActivo()).thenReturn(true);
        when(loc.disponible()).thenReturn(true); when(geo.configurado()).thenReturn(true);
        s = new LugarService(repo, geo, area, hib, loc);
        s.usarGoogle(google);
        s.soloGoogle(true);
    }

    @Test void sugerirNoConsultaOtrosProveedoresAunqueGoogleNoDevuelvaNada() {
        when(google.sugerir(anyString(), any())).thenReturn(List.of());
        s.sugerirDetallado("unicentro", "sesion-abc-123");
        verify(hib, never()).sugerirArcgis(anyString());
        verify(loc, never()).sugerir(anyString(), anyInt());
    }

    @Test void siGoogleFallaNoHayRespaldoSilencioso() {
        when(google.sugerir(anyString(), any())).thenThrow(new IllegalStateException("x"));
        when(google.buscarTexto(anyString())).thenThrow(new IllegalStateException("x"));
        var r = s.buscarDetallado("unicentro", "", "sesion-abc-123");
        assertTrue(r.lugares().isEmpty());
        verify(hib, never()).buscarCatastro(anyString());
        verify(hib, never()).buscarArcgisResultado(anyString(), anyString());
        verify(loc, never()).buscar(anyString(), anyInt());
        verify(geo, never()).buscar(anyString());
        verify(repo, never()).buscarCatalogo(anyString(), anyInt());
    }

    @Test void sinGoogleConfiguradoLaBusquedaLoDiceYNoUsaOtrosProveedores() {
        when(google.activo()).thenReturn(false);
        var sug = s.sugerirDetallado("unicentro", "sesion-abc-123");
        assertTrue(sug.sugerencias().isEmpty());
        assertEquals(EstadoBusqueda.NO_CONFIGURADO, sug.estado(), "no es «sin coincidencias» ni un fallo transitorio");
        var exp = s.buscarDetallado("unicentro", "", "sesion-abc-123");
        assertTrue(exp.lugares().isEmpty());
        assertEquals(EstadoBusqueda.NO_CONFIGURADO, exp.estado());
        assertTrue(exp.avisos().stream().anyMatch(a -> a.startsWith("La búsqueda de Google no está configurada")), exp.avisos().toString());
        var eleg = s.buscarDetallado("unicentro", "g:ChIJabcdefghij123", "sesion-abc-123");
        assertEquals(EstadoBusqueda.NO_CONFIGURADO, eleg.estado());
        assertTrue(eleg.eleccionFallida());
        verifyNoInteractions(hib, loc, geo);
        verify(repo, never()).buscarCatalogo(anyString(), anyInt());
    }

    @Test void lasSugerenciasDeGoogleTraenNombrePrincipalYReferenciaYSuIdentificador() {
        when(google.sugerir(anyString(), any())).thenReturn(List.of(new GoogleDireccionesService.Sugerencia("Unicentro Villavicencio, Villavicencio, Meta", "ChIJabcdefghij123", "Unicentro Villavicencio", "Villavicencio, Meta")));
        var r = s.sugerirDetallado("unicentro", "sesion-abc-123");
        assertEquals(EstadoBusqueda.OK, r.estado());
        var g = r.sugerencias().get(0);
        assertEquals("Unicentro Villavicencio", g.principal());
        assertEquals("Villavicencio, Meta", g.secundario());
        assertEquals("g:ChIJabcdefghij123", g.magicKey(), "la elección viaja por el identificador de Google, no por el texto");
    }

    @Test void elegirUnaPrediccionResuelveSuPlaceIdYNoHaceUnaSegundaBusquedaDeTexto() {
        when(google.resolver(anyString(), any(), any())).thenReturn(new ResultadoLugares(List.of(new LugarResponse(null, "Unicentro", "Cra. 33, Villavicencio", 4.1272, -73.6203, "Google Maps", false, "LUGAR")), 0));
        var r = s.buscarDetallado("Unicentro Villavicencio", "g:ChIJabcdefghij123", "sesion-abc-123");
        assertEquals(EstadoBusqueda.OK, r.estado());
        verify(google).resolver(eq("ChIJabcdefghij123"), eq("Unicentro Villavicencio"), eq("sesion-abc-123"));
        verify(google, never()).buscarTextoResultado(anyString());
        verifyNoInteractions(hib, loc, geo);
    }

    @Test void siGoogleSeCaeLasSugerenciasNoActivanRespaldoNiMuestranOtroProveedor() {
        when(google.sugerir(anyString(), any())).thenThrow(new ProveedorException(EstadoBusqueda.RED, "x"));
        var r = s.sugerirDetallado("unicentro", "sesion-abc-123");
        assertTrue(r.sugerencias().isEmpty());
        assertEquals(EstadoBusqueda.RED, r.estado());
        assertTrue(r.intentos().stream().allMatch(i -> i.proveedor().equals("google")), "solo se intentó Google: " + r.intentos());
        verifyNoInteractions(hib, loc, geo);
    }

    @Test void elDiagnosticoDeConfiguracionNoRevelaValoresSecretos() {
        when(google.tieneClave()).thenReturn(true); when(google.sobreMapaDeGoogle()).thenReturn(true);
        var d = s.diagnosticoBusqueda();
        assertEquals("OK", d.get("motivo"));
        assertEquals(true, d.get("claveDelServidorConfigurada"));
        assertEquals(List.of("google"), d.get("proveedoresDelPasajero"));
        for (Object v : d.values()) assertTrue(v instanceof Boolean || v instanceof String || v instanceof List, "solo estados y nombres: " + v);
        when(google.tieneClave()).thenReturn(false); when(google.activo()).thenReturn(false);
        assertEquals("FALTA_GOOGLE_MAPS_API_KEY", s.diagnosticoBusqueda().get("motivo"));
        when(google.tieneClave()).thenReturn(true); when(google.sobreMapaDeGoogle()).thenReturn(false);
        assertEquals("MAPA_NO_ES_GOOGLE", s.diagnosticoBusqueda().get("motivo"));
    }

    @Test void elPuntoDelMapaNoConsultaNominatim() {
        when(repo.masCercano(anyDouble(), anyDouble(), anyDouble())).thenReturn(Optional.empty());
        LugarResponse l = s.reverso(4.14, -73.63);
        assertTrue(l.nombre().startsWith("Punto en mapa"));
        verify(geo, never()).reverso(anyDouble(), anyDouble());
    }
}
