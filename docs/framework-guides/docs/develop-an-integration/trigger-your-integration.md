---
title: Trigger your Integration
sidebar_label: 🕹️ Trigger your Integration
sidebar_position: 7
---

import ResyncAbortMessage from '@site/docs/_common/resync-abort-message.mdx';

# 🕹️ Trigger your Integration

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import SwaggerGuide from './\_mdx/trigger-swagger-guide.md';
import CurlGuide from './\_mdx/trigger-curl-guide.md';
import PythonGuide from './\_mdx/trigger-python-guide.md';

This guide explains how you can trigger your integration using [Port](https://app.getport.io).

After setting up & running your integration, you can trigger it using Port's UI/API.

Triggering your integration will run the integration resync and will resync all the data from the source into port and
creating new data, update existing data and delete data that no longer exists in the source by doing so.

<ResyncAbortMessage />

## Triggering using Port's UI

1. Login to [Port](https://app.getport.io) and browse to the [builder page](https://app.getport.io/dev-portal).

2. Open the ingest modal by expanding one of the [blueprints](https://docs.port.io/build-your-software-catalog/define-your-data-model/setup-blueprint/) and clicking the ingest button on the blueprint.

   ![Ingest Button](@site/static/img/ingest-button-1.png)

   or

   ![Ingest Button](@site/static/img/ingest-button-2.png)

3. Select the integration you want to trigger a resync for from the list of your installed integrations.
4. Click on the `Resync` button.

   ![Installation Page](@site/static/img/resync-button.png)

## Triggering using Port's API

By patching the integration either with a new configuration or by patching it with no changes, The integration will
detect the trigger and perform a resync.

<Tabs>
    <TabItem value="swagger" label="Swagger" default>
        <SwaggerGuide/>
    </TabItem>
    <TabItem value="curl" label="cURL">
        <CurlGuide/>
    </TabItem>
    <TabItem value="python" label="Python">
        <PythonGuide/>
    </TabItem>
</Tabs>
