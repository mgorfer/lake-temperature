# Testdaten

`hdkaernten_see.json` ist ein gekürzter Auszug der tatsächlichen Antwort von

    https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json

(abgerufen am 04.09.2026). Behalten wurden drei Stationen, die zusammen die
Fälle abdecken, an denen der Adapter scheitern könnte: zwei mit HZB-Nummer
und eine ohne. Die Messreihen sind auf die letzten vier Werte gekürzt.

Quelle: Land Kärnten, Hydrographischer Dienst — Lizenz CC-BY-4.0,
bezogen über data.gv.at. Die Rohdaten sind laut Dienst ungeprüft.

Zweck: Die Tests laufen damit gegen das echte Feldschema statt gegen ein
ausgedachtes. Der Dienst antwortet Rechenzentrums-Adressen nicht, ein
Abruf in der CI ist also keine Möglichkeit.
