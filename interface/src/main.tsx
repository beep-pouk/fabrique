import "@fontsource-variable/inter";
import * as Infobulle from "@radix-ui/react-tooltip";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { FournisseurStudio } from "./studio";
import "./styles.css";

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <Infobulle.Provider delayDuration={300}>
      <FournisseurStudio>
        <App />
      </FournisseurStudio>
    </Infobulle.Provider>
  </StrictMode>,
);
