---
title: 🕹️ Trigger your Integration
sidebar_position: 7
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import SwaggerGuide from './\_mdx/trigger-swagger-guide.md';
import CurlGuide from './\_mdx/trigger-curl-guide.md';
import PythonGuide from './\_mdx/trigger-python-guide.md';

This guide explains how you can trigger your integration using the [Port](https://app.getport.io).

After setting up & running your integration, you can trigger it using the Port UI/ Port API.

Triggering your integration will run the integration resync and will resync all the data from the source into port and
creating new data, update existing data and delete data that no longer exists in the source by doing so.

## Triggering using the Port UI

1. Navigate to the [Port](https://app.getport.io) and login to your account.
2. Click on the

## Triggering using the Port API

By patching the integration either with a new configuration or by patching it with no changes, The integration will
detect the trigger and will run the integration resync.

<Tabs>
    <TabItem value="swagger" label="swagger" default>
        <SwaggerGuide/>
    </TabItem>
    <TabItem value="curl" label="curl">
        <CurlGuide/>
    </TabItem>
    <TabItem value="python" label="python">
        <PythonGuide/>
    </TabItem>
</Tabs>
