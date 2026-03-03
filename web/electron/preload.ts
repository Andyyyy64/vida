import { contextBridge } from 'electron'

// Expose minimal info to the renderer process.
// All data fetching goes through the Hono REST API as usual.
contextBridge.exposeInMainWorld('electron', {
  platform: process.platform,
})
